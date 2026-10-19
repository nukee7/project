"""Shared text cache between primary retrieve and extract tools."""

from __future__ import annotations


class FilingTextStore:
    """In-memory cache mapping source_id → filing text."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    def store(self, source_id: str, text: str) -> None:
        self._cache[source_id] = text

    def get(self, source_id: str) -> str | None:
        return self._cache.get(source_id)

    def has(self, source_id: str) -> bool:
        return source_id in self._cache

    def clear(self) -> None:
        self._cache.clear()
