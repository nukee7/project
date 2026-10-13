"""SEC EDGAR filing retrieval implementation.

Downloads the actual filing document from SEC EDGAR and stores
the text content on the SourceMetadata. Handles HTML filings
by stripping tags to produce clean text.

SEC EDGAR rate limit: max 10 requests per second.
We add a small delay between requests to stay well within limits.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime
from html.parser import HTMLParser

import httpx

from shared.domain.evidence import SourceMetadata
from company_agent.tools.base import RetrieveSourceRecord
from company_agent.tools.edgar.text_store import FilingTextStore

logger = logging.getLogger(__name__)


class _HTMLTextExtractor(HTMLParser):
    """Simple HTML → plain text converter.

    Strips tags, keeps text content. Handles SEC filing HTML
    which is often deeply nested tables and divs.
    """

    def __init__(self) -> None:
        super().__init__()
        self._text_parts: list[str] = []
        self._skip_tags = {"script", "style", "meta", "link"}
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag.lower() in self._skip_tags:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._skip_tags:
            self._skip_depth = max(0, self._skip_depth - 1)
        # Add newlines after block elements
        if tag.lower() in ("p", "div", "tr", "br", "h1", "h2", "h3", "h4", "li"):
            self._text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._text_parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._text_parts)
        # Collapse multiple whitespace/newlines
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _html_to_text(html: str) -> str:
    """Convert HTML to clean plain text."""
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


class EdgarRetrieveSource(RetrieveSourceRecord):
    """Download and process a filing from SEC EDGAR.

    Takes a source_url (from EdgarSearchSources) and downloads the
    actual filing content. Converts HTML to plain text.

    The retrieved text is stored in a new SourceMetadata with updated
    retrieval_time. The text itself is stored in licensing_notes
    temporarily (we'll add a proper content field later) — actually
    we return the SourceMetadata as-is per the interface, and the
    text is available via a separate accessor.

    For now, the filing text is stored as an attribute on the returned
    SourceMetadata object via a subclass.
    """

    # Max text length to keep (10-K filings can be huge)
    MAX_TEXT_LENGTH = 200_000  # ~200K chars, roughly 50K tokens

    def __init__(self, user_agent: str | None = None, text_store: FilingTextStore | None = None) -> None:
        self._user_agent = user_agent or os.getenv(
            "EDGAR_USER_AGENT", "CompanyAgent research@example.com"
        )
        self._headers = {
            "User-Agent": self._user_agent,
            "Accept": "text/html, application/xhtml+xml, text/plain",
        }
        self._text_store = text_store if text_store is not None else FilingTextStore()

    async def retrieve(
        self,
        source_id: str,
        source_url: str | None = None,
    ) -> SourceMetadata | None:
        """Download a filing from SEC EDGAR and return updated metadata.

        The filing text is cached and accessible via get_text(source_id).
        """
        if not source_url:
            logger.warning("No URL provided for source %s", source_id)
            return None

        logger.info("EDGAR retrieve: %s → %s", source_id, source_url)

        try:
            # Respect EDGAR rate limits
            await asyncio.sleep(0.15)

            async with httpx.AsyncClient(
                headers=self._headers,
                timeout=60,
                follow_redirects=True,
            ) as client:
                resp = await client.get(source_url)
                resp.raise_for_status()
                raw_content = resp.text

        except Exception as e:
            logger.error("EDGAR retrieve failed for %s: %s", source_url, e)
            return None

        # Convert HTML to text
        if "<html" in raw_content.lower() or "<body" in raw_content.lower():
            text = _html_to_text(raw_content)
        else:
            text = raw_content

        # Truncate if too long
        if len(text) > self.MAX_TEXT_LENGTH:
            text = text[: self.MAX_TEXT_LENGTH] + "\n\n[TRUNCATED — document exceeds size limit]"
            logger.info(
                "Truncated %s from %d to %d chars",
                source_id, len(raw_content), self.MAX_TEXT_LENGTH,
            )

        # Cache the text
        self._text_store.store(source_id, text)

        logger.info(
            "EDGAR retrieve complete: %s, %d chars of text",
            source_id, len(text),
        )

        return SourceMetadata(
            source_id=source_id,
            publisher="SEC EDGAR",
            title=f"Retrieved: {source_id}",
            source_url=source_url,
            retrieval_time=datetime.now(),
            licensing_notes=f"Public domain — SEC EDGAR. Text length: {len(text)} chars.",
        )

    def get_text(self, source_id: str) -> str | None:
        return self._text_store.get(source_id)

    def clear_cache(self) -> None:
        self._text_store.clear()
