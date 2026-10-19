"""Primary source retrieval — downloads BSE India filings.

Handles PDF attachments, HTML pages, and plain text.
BSE filing attachments are typically PDFs at:
  https://www.bseindia.com/xml-data/corpfiling/AttachLive/{filename}
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from html.parser import HTMLParser

import httpx

from shared.domain.evidence import SourceMetadata
from company_agent.tools.base import RetrieveSourceRecord
from company_agent.tools.primary.text_store import FilingTextStore

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 200_000


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        if tag.lower() in ("p", "div", "tr", "br", "h1", "h2", "h3", "li", "td"):
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


class PrimaryRetrieveSource(RetrieveSourceRecord):
    """Download and process a filing from BSE India."""

    def __init__(self, text_store: FilingTextStore | None = None) -> None:
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html, application/pdf, application/xhtml+xml, */*",
            "Referer": "https://www.bseindia.com/",
        }
        self._text_store = text_store if text_store is not None else FilingTextStore()

    async def retrieve(self, source_id: str, source_url: str | None = None) -> SourceMetadata | None:
        if not source_url:
            logger.warning("No URL for source %s", source_id)
            return None

        logger.info("Primary retrieve: %s → %s", source_id, source_url)

        try:
            await asyncio.sleep(0.3)
            async with httpx.AsyncClient(headers=self._headers, timeout=30, follow_redirects=True) as client:
                resp = await client.get(source_url)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                raw = resp.content
        except Exception as e:
            logger.error("Primary retrieve failed for %s: %s", source_url, e)
            return None

        text = ""
        if "pdf" in content_type.lower() or source_url.lower().endswith(".pdf"):
            text = self._extract_pdf_text(raw, source_id)
        elif "html" in content_type.lower() or source_url.lower().endswith((".htm", ".html")):
            text = _html_to_text(raw.decode("utf-8", errors="replace"))
        else:
            text = raw.decode("utf-8", errors="replace")

        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH] + "\n\n[TRUNCATED]"

        self._text_store.store(source_id, text)
        logger.info("Primary retrieve complete: %s, %d chars", source_id, len(text))

        return SourceMetadata(
            source_id=source_id, publisher="BSE India",
            title=f"Retrieved: {source_id}", source_url=source_url,
            retrieval_time=datetime.now(),
            licensing_notes=f"BSE India filing. Text: {len(text)} chars.",
        )

    def _extract_pdf_text(self, pdf_bytes: bytes, source_id: str) -> str:
        try:
            import pdfplumber
            import io
            pages: list[str] = []
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        pages.append(t)
            if pages:
                return "\n\n".join(pages)
        except ImportError:
            pass
        except Exception as e:
            logger.warning("pdfplumber failed for %s: %s", source_id, e)

        try:
            from PyPDF2 import PdfReader
            import io
            reader = PdfReader(io.BytesIO(pdf_bytes))
            pages = [p.extract_text() for p in reader.pages if p.extract_text()]
            if pages:
                return "\n\n".join(pages)
        except ImportError:
            pass
        except Exception as e:
            logger.warning("PyPDF2 failed for %s: %s", source_id, e)

        return "[PDF — install pdfplumber for text extraction: pip install pdfplumber]"

    def get_text(self, source_id: str) -> str | None:
        return self._text_store.get(source_id)

    def clear_cache(self) -> None:
        self._text_store.clear()
