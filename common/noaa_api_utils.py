#!/usr/bin/env python3
"""
Shared NOAA API Utilities
Common functions for making API calls to NOAA endpoints with error handling and rate limiting
"""

import logging
import time
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class NOAAPIManager:
    """Manager for NOAA API interactions with common utilities"""

    def __init__(
        self,
        base_url: str,
        user_agent: str = "NOAA_Federated_DataLake/1.0",
        rate_limit: float = 1.0,
    ):
        """
        Initialize NOAA API manager

        Args:
            base_url: Base URL for the NOAA API
            user_agent: User agent string for requests
            rate_limit: Minimum seconds between requests (rate limiting)
        """
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.rate_limit = rate_limit
        self.last_request_time = 0

    def make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        timeout: int = 30,
        retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to NOAA API with error handling and rate limiting

        Args:
            endpoint: API endpoint (will be appended to base_url)
            params: Query parameters
            method: HTTP method (GET, POST, etc.)
            timeout: Request timeout in seconds
            retries: Number of retry attempts on failure

        Returns:
            Dict containing response data or error information

        Raises:
            Exception: For critical errors after all retries
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}" if endpoint else self.base_url

        # Rate limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            sleep_time = self.rate_limit - elapsed
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

        headers = {"User-Agent": self.user_agent}

        for attempt in range(retries + 1):
            try:
                self.last_request_time = time.time()

                logger.debug(f"Making {method} request to {url} with params {params}")

                if method.upper() == "GET":
                    response = requests.get(
                        url, params=params, headers=headers, timeout=timeout
                    )
                else:
                    # For future expansion if needed
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()

                # Try to parse JSON, fallback to text
                try:
                    data = response.json()
                except ValueError:
                    data = {"text": response.text}

                logger.debug(f"Successful request to {url}")
                return {
                    "success": True,
                    "data": data,
                    "status_code": response.status_code,
                    "url": response.url,
                }

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1} for {url}")
                if attempt < retries:
                    time.sleep(2**attempt)  # Exponential backoff
                    continue

            except requests.exceptions.HTTPError as e:
                logger.warning(f"HTTP error on attempt {attempt + 1} for {url}: {e}")
                if (
                    response.status_code >= 500 and attempt < retries
                ):  # Retry server errors
                    time.sleep(2**attempt)
                    continue

            except requests.exceptions.RequestException as e:
                logger.error(f"Request error on attempt {attempt + 1} for {url}: {e}")
                if attempt < retries:
                    time.sleep(2**attempt)
                    continue

        # All retries failed
        return {
            "success": False,
            "error": f"Failed to fetch data from {url} after {retries + 1} attempts",
            "url": url,
        }


# Pre-configured managers for common NOAA APIs
NWS_MANAGER = NOAAPIManager("https://api.weather.gov")
TIDES_MANAGER = NOAAPIManager(
    "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
)
CDO_MANAGER = NOAAPIManager("https://www.ncdc.noaa.gov/cdo-web/api/v2")
NDBC_MANAGER = NOAAPIManager("https://www.ndbc.noaa.gov/data/realtime2")
NCEI_MANAGER = NOAAPIManager("https://www.ncei.noaa.gov/access/services")
