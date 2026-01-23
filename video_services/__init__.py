"""
Video Services Auto-Discovery System
Multi-service video downloader with plugin-based architecture
"""

import os
import re
import importlib
import inspect
import logging
from typing import List, Type, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class BaseProvider:
    """Base class for all video providers."""

    # Subclasses should define PROVIDER_NAME for auto-generation of env vars
    PROVIDER_NAME = None

    # Or define these explicitly (auto-generated from PROVIDER_NAME if not set)
    API_KEY_ENV_VAR = None
    PRIORITY_ENV_VAR = None

    # Default priority if not specified in environment (0-100, higher = tried first)
    DEFAULT_PRIORITY = 50

    def __init__(self, name: str):
        self.name = name
        self.priority = self.DEFAULT_PRIORITY

    def get_video_url(self, url: str) -> Optional[str]:
        """
        Get video download URL from video link.

        Args:
            url: Video URL to process

        Returns:
            Video download URL, or None on error
        """
        raise NotImplementedError("Subclass must implement get_video_url()")

    def __str__(self) -> str:
        return self.name


class BaseService:
    """Base class for all video services."""

    # Subclasses MUST define these
    SERVICE_NAME = None           # e.g., "INSTAGRAM"
    URL_PATTERN = None            # Regex for URL matching
    DEFAULT_PRIORITY = 50         # Service priority (0-100)
    PROVIDER_BASE_CLASS = BaseProvider  # Base class for this service's providers

    def __init__(self):
        self.providers = []
        self.priority = self.DEFAULT_PRIORITY
        self._load_service_priority()

    def _load_service_priority(self):
        """Load service priority from environment variable."""
        if self.SERVICE_NAME:
            priority_env_var = f"{self.SERVICE_NAME}_PRIORITY"
            priority_str = os.getenv(priority_env_var)
            if priority_str:
                try:
                    self.priority = max(0, min(100, int(priority_str)))
                except ValueError:
                    logger.warning(f"Invalid priority for {self.SERVICE_NAME}: {priority_str}, using default")

    def matches_url(self, url: str) -> bool:
        """
        Check if URL matches this service's pattern.

        Args:
            url: URL to check

        Returns:
            True if URL matches this service
        """
        if not self.URL_PATTERN:
            return False
        return bool(re.search(self.URL_PATTERN, url))

    def extract_url(self, text: str) -> Optional[str]:
        """
        Extract first matching URL from text.

        Args:
            text: Message text to search

        Returns:
            First matching URL found, or None
        """
        if not text or not self.URL_PATTERN:
            return None

        match = re.search(self.URL_PATTERN, text)
        return match.group(0) if match else None

    def discover_providers(self) -> List[Type[BaseProvider]]:
        """
        Automatically discover all provider classes in this service's providers folder.

        Returns:
            List of provider classes (not instances)
        """
        providers = []

        # Get the service's module directory
        service_module = inspect.getmodule(self.__class__)
        if not service_module or not service_module.__file__:
            return providers

        service_dir = Path(service_module.__file__).parent
        providers_dir = service_dir / "providers"

        if not providers_dir.exists():
            logger.warning(f"No providers folder found for {self.SERVICE_NAME}")
            return providers

        # Get all .py files in providers/ except __init__.py
        for file_path in providers_dir.glob("*.py"):
            if file_path.name.startswith("_"):
                continue

            # Import the module
            module_name = file_path.stem
            try:
                # Get the service's package name
                service_package = service_module.__package__
                module = importlib.import_module(f"{service_package}.providers.{module_name}")

                # Find all classes that inherit from this service's PROVIDER_BASE_CLASS
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    # Check if it's a subclass but not the base class itself
                    if (issubclass(obj, self.PROVIDER_BASE_CLASS) and
                        obj is not self.PROVIDER_BASE_CLASS and
                        obj.__module__ == module.__name__):
                        providers.append(obj)

            except Exception as e:
                logger.error(f"Could not load provider from {module_name}: {e}")

        return providers

    def load_providers_from_env(self) -> List[BaseProvider]:
        """
        Load and initialize providers based on environment variables.

        Each provider defines PROVIDER_NAME which auto-generates:
        - {PROVIDER_NAME}_API_KEY
        - {PROVIDER_NAME}_PRIORITY (optional, 0-100)

        Returns:
            List of initialized provider instances (sorted by priority, highest first)
        """
        # Discover all available provider classes
        provider_classes = self.discover_providers()

        if not provider_classes:
            logger.warning(f"No providers found for {self.SERVICE_NAME}")
            return []

        initialized_providers = []

        # Try to initialize each provider
        for provider_class in provider_classes:
            # Auto-generate env var names from PROVIDER_NAME if not explicitly set
            if hasattr(provider_class, 'PROVIDER_NAME') and provider_class.PROVIDER_NAME:
                provider_name = provider_class.PROVIDER_NAME
                api_key_env_var = provider_class.API_KEY_ENV_VAR or f"{provider_name}_API_KEY"
                priority_env_var = provider_class.PRIORITY_ENV_VAR or f"{provider_name}_PRIORITY"
            elif hasattr(provider_class, 'API_KEY_ENV_VAR') and provider_class.API_KEY_ENV_VAR:
                # Fallback: use explicit API_KEY_ENV_VAR
                api_key_env_var = provider_class.API_KEY_ENV_VAR
                priority_env_var = provider_class.PRIORITY_ENV_VAR
            else:
                logger.warning(f"Skipping {provider_class.__name__} - PROVIDER_NAME or API_KEY_ENV_VAR not defined")
                continue

            # Get API key from environment
            api_key = os.getenv(api_key_env_var)

            if api_key:
                try:
                    # Initialize provider with API key
                    provider = provider_class(api_key)

                    # Set priority from environment or use default
                    if priority_env_var:
                        priority_str = os.getenv(priority_env_var)
                        if priority_str:
                            try:
                                provider.priority = max(0, min(100, int(priority_str)))
                            except ValueError:
                                logger.warning(f"Invalid priority for {provider.name}: {priority_str}, using default")

                    initialized_providers.append(provider)
                    logger.info(f"  ✓ Loaded {provider.name} (priority: {provider.priority})")
                except Exception as e:
                    logger.error(f"  ✗ Failed to initialize {provider_class.__name__}: {e}")
            else:
                logger.debug(f"  Skipping {provider_class.__name__} - {api_key_env_var} not set")

        # Sort by priority (highest first)
        initialized_providers.sort(key=lambda p: p.priority, reverse=True)

        return initialized_providers

    def get_video_url(self, url: str) -> Optional[Tuple[str, int, str]]:
        """
        Try to get video URL using configured providers with fallback.

        Args:
            url: Video URL to process

        Returns:
            Tuple of (video_url, provider_number, provider_name) or None if all fail
        """
        logger.info(f"[SERVICE:{self.SERVICE_NAME}] Starting provider fallback chain...")
        logger.info(f"[SERVICE:{self.SERVICE_NAME}] Input URL: {url}")

        if not self.providers:
            logger.warning(f"[SERVICE:{self.SERVICE_NAME}] ✗ No providers configured")
            return None

        logger.info(f"[SERVICE:{self.SERVICE_NAME}] Total providers: {len(self.providers)}")

        for i, provider in enumerate(self.providers, 1):
            logger.info(f"[SERVICE:{self.SERVICE_NAME}] {'='*50}")
            logger.info(f"[SERVICE:{self.SERVICE_NAME}] Provider {i}/{len(self.providers)}: {provider.name}")
            logger.info(f"[SERVICE:{self.SERVICE_NAME}] Priority: {provider.priority}")

            try:
                logger.info(f"[SERVICE:{self.SERVICE_NAME}] Calling {provider.name}.get_video_url()...")
                video_url = provider.get_video_url(url)

                if video_url:
                    logger.info(f"[SERVICE:{self.SERVICE_NAME}] ✓ SUCCESS with provider: {provider.name}")
                    logger.info(f"[SERVICE:{self.SERVICE_NAME}] Video URL: {video_url[:100]}...")
                    return (video_url, i, provider.name)
                else:
                    logger.warning(f"[SERVICE:{self.SERVICE_NAME}] ✗ Provider {provider.name} returned None (no video URL)")

            except Exception as e:
                logger.error(f"[SERVICE:{self.SERVICE_NAME}] ✗ Provider {provider.name} raised exception: {type(e).__name__}: {e}", exc_info=True)

        logger.error(f"[SERVICE:{self.SERVICE_NAME}] ✗ ALL {len(self.providers)} provider(s) FAILED")
        return None


def discover_services() -> List[Type[BaseService]]:
    """
    Automatically discover all service classes in the video_services folder.

    Returns:
        List of service classes (not instances)
    """
    services = []
    current_dir = Path(__file__).parent

    # Get all subdirectories in video_services/
    for service_dir in current_dir.iterdir():
        if not service_dir.is_dir() or service_dir.name.startswith("_"):
            continue

        # Check if __init__.py exists
        init_file = service_dir / "__init__.py"
        if not init_file.exists():
            continue

        # Import the module
        service_name = service_dir.name
        try:
            module = importlib.import_module(f"video_services.{service_name}")

            # Find all classes that inherit from BaseService
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Check if it's a subclass of BaseService but not the base class itself
                if (issubclass(obj, BaseService) and
                    obj is not BaseService and
                    obj.__module__ == module.__name__):
                    services.append(obj)

        except Exception as e:
            logger.error(f"Could not load service from {service_name}: {e}")

    return services


def load_services_from_env() -> List[BaseService]:
    """
    Load and initialize services based on environment variables.

    Each service auto-loads its own providers from its providers/ subfolder.

    Returns:
        List of initialized service instances (sorted by priority, highest first)
    """
    # Discover all available service classes
    service_classes = discover_services()

    if not service_classes:
        raise ValueError("No services found in video_services folder!")

    initialized_services = []

    logger.info("="*60)
    logger.info("Auto-discovering video services...")
    logger.info("="*60)

    # Initialize each service
    for service_class in service_classes:
        try:
            service = service_class()

            # Load providers for this service
            logger.info(f"Loading providers for {service.SERVICE_NAME}...")
            service.providers = service.load_providers_from_env()

            if service.providers:
                initialized_services.append(service)
                logger.info(f"✓ Loaded service: {service.SERVICE_NAME} with {len(service.providers)} provider(s) (priority: {service.priority})")
            else:
                logger.warning(f"⚠ Service {service.SERVICE_NAME} has no providers configured, skipping")

        except Exception as e:
            logger.error(f"✗ Failed to initialize {service_class.__name__}: {e}")

    if not initialized_services:
        raise ValueError("No services could be initialized! Check your environment variables.")

    # Sort by priority (highest first)
    initialized_services.sort(key=lambda s: s.priority, reverse=True)

    logger.info("="*60)
    logger.info(f"Total services loaded: {len(initialized_services)}")
    logger.info("="*60)

    return initialized_services


__all__ = ['BaseProvider', 'BaseService', 'discover_services', 'load_services_from_env']
