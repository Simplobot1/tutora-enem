from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from app.services.ocr_service import OcrResult

logger = logging.getLogger(__name__)

# Default TTL: 7 days
DEFAULT_TTL_DAYS = 7


class OcrCache:
    """
    In-memory cache for OCR results, keyed by Telegram file_id.
    Implements simple TTL expiration (7 days by default).
    """

    def __init__(self, ttl_days: int = DEFAULT_TTL_DAYS) -> None:
        self.ttl_days = ttl_days
        self._cache: dict[str, tuple[OcrResult, datetime]] = {}

    def get(self, file_id: str) -> OcrResult | None:
        """
        Retrieve cached OCR result if it exists and hasn't expired.

        Args:
            file_id: Telegram file_id

        Returns:
            OcrResult if cached and fresh, None otherwise
        """
        if file_id not in self._cache:
            return None

        result, timestamp = self._cache[file_id]
        age = datetime.now() - timestamp
        ttl = timedelta(days=self.ttl_days)

        if age > ttl:
            # Expired, remove from cache
            del self._cache[file_id]
            logger.debug("OCR cache expired for file_id %s (age: %s)", file_id, age)
            return None

        logger.debug("OCR cache hit for file_id %s (age: %s)", file_id, age)
        return result

    def set(self, file_id: str, result: OcrResult) -> None:
        """
        Store OCR result in cache.

        Args:
            file_id: Telegram file_id
            result: OcrResult to cache
        """
        self._cache[file_id] = (result, datetime.now())
        logger.debug("OCR result cached for file_id %s", file_id)

    def clear(self) -> None:
        """Clear entire cache (for testing or reset)."""
        self._cache.clear()
        logger.debug("OCR cache cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        return {
            "total_entries": len(self._cache),
            "ttl_days": self.ttl_days,
        }
