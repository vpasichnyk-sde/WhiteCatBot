#!/usr/bin/env python3
"""
Service Router for Multi-Service Video Downloader
Routes URLs to appropriate services with priority-based fallback
"""

import logging
from typing import List, Optional, Tuple
from video_services import BaseService

logger = logging.getLogger(__name__)


class ServiceRouter:
    """
    Routes video URLs to appropriate services with automatic fallback.

    The router tries services by priority until one successfully matches and downloads.
    """

    def __init__(self, services: List[BaseService]):
        """
        Initialize service router.

        Args:
            services: List of service instances in priority order
        """
        if not services:
            raise ValueError("At least one service must be configured")

        self.services = services
        logger.info(f"ServiceRouter initialized with {len(services)} service(s): {[s.SERVICE_NAME for s in services]}")

    def get_video_url(self, text: str):
        """
        Extract URL from text and get video download URL using appropriate service.

        Args:
            text: Message text to search for video URLs

        Returns:
            Tuple of (video_url, service_name, provider_number, provider_name) if successful
            "providers_failed" if URL matched but all providers failed
            None if no URL pattern matched
        """
        logger.info(f"[ROUTER] Starting service routing...")
        logger.info(f"[ROUTER] Input text: {text[:200] if text else 'None'}")

        if not text:
            logger.info(f"[ROUTER] No text provided, returning None")
            return None

        logger.info(f"[ROUTER] Available services: {len(self.services)}")
        for idx, svc in enumerate(self.services, 1):
            logger.info(f"[ROUTER]   {idx}. {svc.SERVICE_NAME} (priority: {svc.priority})")

        # Try each service by priority
        for service in self.services:
            logger.info(f"[ROUTER] Trying service: {service.SERVICE_NAME}")
            logger.info(f"[ROUTER] URL pattern: {service.URL_PATTERN}")

            # Try to extract URL for this service
            url = service.extract_url(text)

            if url:
                logger.info(f"[ROUTER] ✓ URL matched service: {service.SERVICE_NAME}")
                logger.info(f"[ROUTER] Extracted URL: {url}")

                # Try to get video URL using this service's providers
                logger.info(f"[ROUTER] Calling {service.SERVICE_NAME}.get_video_url()...")
                result = service.get_video_url(url)

                if result:
                    video_url, provider_num, provider_name = result
                    logger.info(f"[ROUTER] ✓ Video URL obtained from {service.SERVICE_NAME}")
                    logger.info(f"[ROUTER] Provider: #{provider_num} - {provider_name}")
                    logger.info(f"[ROUTER] Video URL: {video_url[:100]}...")
                    return (video_url, service.SERVICE_NAME, provider_num, provider_name)
                else:
                    # Service matched but all providers failed
                    logger.warning(f"[ROUTER] ✗ Service {service.SERVICE_NAME} matched URL but all providers failed")
                    return "providers_failed"
            else:
                logger.info(f"[ROUTER] No URL match for {service.SERVICE_NAME}")

        # No service matched
        logger.info(f"[ROUTER] ✗ No service matched any URL in text")
        return None

    def add_service(self, service: BaseService) -> None:
        """
        Add a new service to the end of the list.

        Args:
            service: Service instance to add
        """
        self.services.append(service)
        logger.info(f"Added service: {service.SERVICE_NAME}")

    def remove_service(self, service_name: str) -> bool:
        """
        Remove a service by name.

        Args:
            service_name: Name of service to remove

        Returns:
            True if service was removed, False if not found
        """
        for i, service in enumerate(self.services):
            if service.SERVICE_NAME == service_name:
                self.services.pop(i)
                logger.info(f"Removed service: {service_name}")
                return True

        logger.warning(f"Service not found: {service_name}")
        return False

    def get_services(self) -> List[str]:
        """
        Get list of configured service names.

        Returns:
            List of service names in priority order
        """
        return [service.SERVICE_NAME for service in self.services]
