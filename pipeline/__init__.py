"""
Pipeline architecture for message processing.

This module provides a flexible pipeline system where messages flow through
a series of handlers. Each handler can process the message and optionally
stop further processing.

Usage:
    from pipeline import MessagePipeline, PipelineContext, PipelineHandler
    from pipeline.handlers import SecretFileHandler, VideoDownloadHandler

    pipeline = MessagePipeline()
    pipeline.add_handler(SecretFileHandler("secret.txt"))
    pipeline.add_handler(VideoDownloadHandler(service_router))

    # In your message handler:
    await pipeline.run(update, context)
"""

import os
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """
    Context object that flows through the pipeline.

    Attributes:
        update: Telegram Update object
        context: Telegram callback context
        should_continue: If False, pipeline stops after current handler
        data: Shared dictionary for handlers to pass data to each other
    """
    update: Update
    context: ContextTypes.DEFAULT_TYPE
    should_continue: bool = True
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def message(self):
        """Convenience property to access the message."""
        return self.update.message

    @property
    def message_text(self) -> Optional[str]:
        """Convenience property to access message text."""
        if self.message:
            return self.message.text
        return None

    def stop(self) -> None:
        """Stop the pipeline after current handler."""
        self.should_continue = False


class PipelineHandler(ABC):
    """
    Abstract base class for pipeline handlers.

    Each handler processes the message and can optionally stop the pipeline
    by calling ctx.stop() or setting ctx.should_continue = False.

    Subclasses must implement the process() method.
    """

    # Default priority (0-100, higher runs first)
    DEFAULT_PRIORITY = 50

    # Handler name for env var generation (e.g., "VIDEO_DOWNLOAD")
    HANDLER_NAME = None

    def __init__(self, name: Optional[str] = None):
        """
        Initialize the handler.

        Args:
            name: Optional handler name for logging (defaults to class name)
        """
        self.name = name or self.__class__.__name__
        self.priority = self.DEFAULT_PRIORITY

    @abstractmethod
    async def process(self, ctx: PipelineContext) -> None:
        """
        Process the message.

        Args:
            ctx: Pipeline context containing update, message, and shared data.
                 Call ctx.stop() to prevent further handlers from running.
        """
        pass

    async def should_process(self, ctx: PipelineContext) -> bool:
        """
        Optional hook to determine if this handler should process the message.

        Override this method to add conditions for when the handler should run.
        Default implementation always returns True.

        Args:
            ctx: Pipeline context

        Returns:
            True if handler should process, False to skip
        """
        return True


class MessagePipeline:
    """
    Manages the message processing pipeline.

    Handlers are executed in the order they were added. If any handler
    sets ctx.should_continue = False or calls ctx.stop(), the pipeline
    stops and remaining handlers are not executed.

    Example:
        pipeline = MessagePipeline()
        pipeline.add_handler(LoggingHandler())
        pipeline.add_handler(SpamFilterHandler())
        pipeline.add_handler(VideoDownloadHandler())

        # In Telegram handler:
        await pipeline.run(update, context)
    """

    def __init__(self, stop_on_error: bool = True):
        """
        Initialize the pipeline.

        Args:
            stop_on_error: If True, stop pipeline when a handler raises an exception.
                          If False, log the error and continue to next handler.
        """
        self.handlers: list[PipelineHandler] = []
        self.stop_on_error = stop_on_error

    def add_handler(self, handler: PipelineHandler) -> "MessagePipeline":
        """
        Add a handler to the pipeline.

        Args:
            handler: Handler to add

        Returns:
            Self for method chaining
        """
        self.handlers.append(handler)
        logger.debug(f"[PIPELINE] Added handler: {handler.name}")
        return self

    def remove_handler(self, handler: PipelineHandler) -> bool:
        """
        Remove a handler from the pipeline.

        Args:
            handler: Handler to remove

        Returns:
            True if handler was found and removed, False otherwise
        """
        try:
            self.handlers.remove(handler)
            logger.debug(f"[PIPELINE] Removed handler: {handler.name}")
            return True
        except ValueError:
            return False

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> PipelineContext:
        """
        Run the pipeline for a message.

        Args:
            update: Telegram Update object
            context: Telegram callback context

        Returns:
            The PipelineContext after all handlers have run (or pipeline stopped)
        """
        ctx = PipelineContext(update=update, context=context)

        logger.info(f"[PIPELINE] ========== PIPELINE START ==========")
        logger.info(f"[PIPELINE] Handlers: {[h.name for h in self.handlers]}")

        for i, handler in enumerate(self.handlers, 1):
            if not ctx.should_continue:
                logger.info(f"[PIPELINE] Pipeline stopped before handler {i}/{len(self.handlers)}: {handler.name}")
                break

            # Check if handler wants to process this message
            try:
                should_process = await handler.should_process(ctx)
                if not should_process:
                    logger.debug(f"[PIPELINE] Handler {handler.name} skipped (should_process=False)")
                    continue
            except Exception as e:
                logger.error(f"[PIPELINE] Error in {handler.name}.should_process(): {e}")
                if self.stop_on_error:
                    break
                continue

            # Process the message
            logger.info(f"[PIPELINE] Running handler {i}/{len(self.handlers)}: {handler.name}")
            try:
                await handler.process(ctx)
                logger.debug(f"[PIPELINE] Handler {handler.name} completed, should_continue={ctx.should_continue}")
            except Exception as e:
                logger.error(f"[PIPELINE] Error in {handler.name}.process(): {e}", exc_info=True)
                if self.stop_on_error:
                    ctx.stop()
                    break

        logger.info(f"[PIPELINE] ========== PIPELINE END ==========")
        return ctx


def discover_handlers(handlers_dir: str = "handlers") -> list[type[PipelineHandler]]:
    """
    Automatically discover all handler classes in the specified directory.

    Args:
        handlers_dir: Directory name to scan for handlers (relative to project root)

    Returns:
        List of handler classes (not instances)
    """
    import os
    import importlib
    import inspect
    from pathlib import Path

    handlers = []

    # Get handlers directory
    handlers_path = Path(handlers_dir)
    if not handlers_path.exists():
        logger.warning(f"Handlers directory not found: {handlers_dir}")
        return handlers

    # Get all .py files in handlers/ directory
    for file_path in handlers_path.glob("*.py"):
        if file_path.name.startswith("_"):
            continue

        # Import the module
        module_name = file_path.stem
        try:
            # Import from handlers.module_name
            module = importlib.import_module(f"{handlers_dir}.{module_name}")

            # Find all classes that inherit from PipelineHandler
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, PipelineHandler) and
                    obj is not PipelineHandler and
                    obj.__module__ == module.__name__):
                    handlers.append(obj)
                    logger.debug(f"Discovered handler: {obj.__name__} from {module_name}")

        except Exception as e:
            logger.error(f"Could not load handler from {module_name}: {e}")

    return handlers


def load_handlers_from_env(handlers_dir: str = "handlers") -> list[PipelineHandler]:
    """
    Load and initialize handlers with priority sorting.

    Each handler can optionally define:
    - HANDLER_NAME: For env var generation (e.g., "VIDEO_DOWNLOAD")
    - DEFAULT_PRIORITY: Priority value (0-100, higher runs first)

    Environment variables:
    - {HANDLER_NAME}_PRIORITY: Override handler priority
    - {HANDLER_NAME}_ENABLED: Set to "false" to disable handler

    Args:
        handlers_dir: Directory to scan for handlers

    Returns:
        List of initialized handler instances (sorted by priority, highest first)
    """
    # Discover all available handler classes
    handler_classes = discover_handlers(handlers_dir)

    if not handler_classes:
        logger.warning(f"No handlers found in {handlers_dir}/")
        return []

    initialized_handlers = []

    logger.info("="*60)
    logger.info("Auto-discovering pipeline handlers...")
    logger.info("="*60)

    # Initialize each handler
    for handler_class in handler_classes:
        try:
            # Create instance
            handler = handler_class()

            # Load priority from environment if HANDLER_NAME is defined
            if hasattr(handler_class, 'HANDLER_NAME') and handler_class.HANDLER_NAME:
                handler_name = handler_class.HANDLER_NAME

                # Check if handler is disabled
                enabled_env = f"{handler_name}_ENABLED"
                if os.getenv(enabled_env, "true").lower() == "false":
                    logger.info(f"  ⊘ Skipping {handler.name} (disabled via {enabled_env})")
                    continue

                # Load priority override
                priority_env = f"{handler_name}_PRIORITY"
                priority_str = os.getenv(priority_env)
                if priority_str:
                    try:
                        handler.priority = max(0, min(100, int(priority_str)))
                        logger.debug(f"  Set priority for {handler.name}: {handler.priority}")
                    except ValueError:
                        logger.warning(f"  Invalid priority for {handler.name}: {priority_str}")

            initialized_handlers.append(handler)
            logger.info(f"  ✓ Loaded {handler.name} (priority: {handler.priority})")

        except Exception as e:
            logger.error(f"  ✗ Failed to initialize {handler_class.__name__}: {e}")

    # Sort by priority (highest first)
    initialized_handlers.sort(key=lambda h: h.priority, reverse=True)

    logger.info("="*60)
    logger.info(f"Total handlers loaded: {len(initialized_handlers)}")
    logger.info("="*60)

    return initialized_handlers


__all__ = [
    'PipelineContext',
    'PipelineHandler',
    'MessagePipeline',
    'discover_handlers',
    'load_handlers_from_env'
]
