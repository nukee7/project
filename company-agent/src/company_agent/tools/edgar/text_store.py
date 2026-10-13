"""Shared text cache between EDGAR retrieve and extract tools.

When EdgarRetrieveSource downloads a filing, it stores the text here.
When EdgarExtractEvidence needs to parse a filing, it reads from here.
"""

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

    def __len__(self) -> int:
        return len(self._cache)
