"""Primary source evidence extractor — Indian corporate filings.

Indian annual reports and financial results don't have the rigid
Item 1/1A/7 structure of US 10-K filings. Instead they typically have:

Annual Reports:
  - Director's Report
  - Management Discussion & Analysis (MD&A)
  - Auditor's Report
  - Financial Statements (Balance Sheet, P&L, Cash Flow)
  - Notes to Accounts
  - Corporate Governance Report

Quarterly Financial Results:
  - Usually a single-page tabular format with key line items
  - Revenue, expenses, profit before/after tax, EPS

Since Indian filing formats are less standardized, this extractor
uses broader section detection patterns and falls back to chunked
extraction for unstructured text.
"""

from __future__ import annotations

import logging
import re
import uuid

from shared.domain.evidence import EvidenceRecord, SourceMetadata
from company_agent.tools.base import ExtractEvidence
from company_agent.tools.primary.text_store import FilingTextStore

logger = logging.getLogger(__name__)

MAX_EXCERPT_LENGTH = 3000


def _uid() -> str:
    return uuid.uuid4().hex[:12]


# Indian filing section patterns
_INDIAN_SECTIONS = [
    {
        "name": "Management Discussion & Analysis",
        "pattern": r"(?:Management\s+Discussion\s+(?:and|&)\s+Analysis|MD\s*&\s*A|MDA)",
        "tags": ["mda", "financial_analysis", "revenue", "expenses", "outlook"],
        "is_management_statement": True,
    },
    {
        "name": "Director's Report",
        "pattern": r"(?:Director(?:'?s)?\s+Report|DIRECTORS?\s+REPORT)",
        "tags": ["directors_report", "governance", "strategy", "dividends"],
        "is_management_statement": True,
    },
    {
        "name": "Auditor's Report",
        "pattern": r"(?:Auditor(?:'?s)?\s+Report|INDEPENDENT\s+AUDITOR|AUDIT\s+REPORT)",
        "tags": ["auditor", "audit", "financial_statements"],
        "is_management_statement": False,
    },
    {
        "name": "Corporate Governance",
        "pattern": r"(?:Corporate\s+Governance|CORPORATE\s+GOVERNANCE)",
        "tags": ["governance", "board", "compliance"],
        "is_management_statement": False,
    },
    {
        "name": "Risk Management",
        "pattern": r"(?:Risk\s+Management|RISK\s+MANAGEMENT|Risk\s+Factors|RISK\s+FACTORS)",
        "tags": ["risks", "risk_management", "risk_factors"],
        "is_management_statement": True,
    },
    {
        "name": "Financial Statements",
        "pattern": r"(?:Balance\s+Sheet|BALANCE\s+SHEET|Statement\s+of\s+Profit|PROFIT\s+AND\s+LOSS|Cash\s+Flow|CASH\s+FLOW)",
        "tags": ["financial_statements", "balance_sheet", "profit_loss", "cash_flow"],
        "is_management_statement": False,
    },
    {
        "name": "Business Overview",
        "pattern": r"(?:Business\s+Overview|BUSINESS\s+OVERVIEW|About\s+(?:the\s+)?Company|ABOUT\s+(?:THE\s+)?COMPANY|Company\s+Overview)",
        "tags": ["business", "overview", "products", "revenue_drivers"],
        "is_management_statement": False,
    },
    {
        "name": "Shareholding Pattern",
        "pattern": r"(?:Shareholding\s+Pattern|SHAREHOLDING\s+PATTERN|Share\s+Holding)",
        "tags": ["shareholding", "ownership", "promoters"],
        "is_management_statement": False,
    },
]


def _find_sections(text: str, section_defs: list[dict]) -> list[dict]:
    matches: list[dict] = []
    for sec_def in section_defs:
        for m in re.finditer(sec_def["pattern"], text, re.IGNORECASE):
            matches.append({
                "name": sec_def["name"],
                "start": m.start(),
                "tags": sec_def["tags"],
                "is_management_statement": sec_def["is_management_statement"],
            })
    matches.sort(key=lambda x: x["start"])
    for i in range(len(matches)):
        matches[i]["end"] = matches[i + 1]["start"] if i + 1 < len(matches) else len(text)
    return matches


def _clean_excerpt(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class PrimaryExtractEvidence(ExtractEvidence):
    """Extract evidence records from Indian corporate filings.

    Reads filing text from the shared FilingTextStore, identifies
    known sections, and creates EvidenceRecord objects.
    Falls back to chunked extraction if no sections are found.
    """

    def __init__(self, text_store: FilingTextStore) -> None:
        self._text_store = text_store

    async def extract(
        self,
        source: SourceMetadata,
        extraction_query: str,
        scope: str | None = None,
    ) -> list[EvidenceRecord]:
        source_id = source.source_id
        text = self._text_store.get(source_id)

        if not text:
            logger.warning("No cached text for %s — skipping", source_id)
            return []

        logger.info("Extracting from %s (%d chars), query='%s'", source_id, len(text), extraction_query[:80])

        sections = _find_sections(text, _INDIAN_SECTIONS)

        if not sections:
            logger.info("No known sections — using chunked extraction")
            return self._chunked_extract(text, source, scope)

        records: list[EvidenceRecord] = []
        for section in sections:
            section_text = text[section["start"]:section["end"]]
            excerpt = _clean_excerpt(section_text)

            if len(excerpt) < 50:
                continue
            if len(excerpt) > MAX_EXCERPT_LENGTH:
                excerpt = excerpt[:MAX_EXCERPT_LENGTH] + " [TRUNCATED]"

            records.append(EvidenceRecord(
                evidence_id=f"ev_{_uid()}",
                source=source,
                excerpt=excerpt,
                locator=f"Indian Filing — {section['name']}",
                applicable_period=source.reporting_period,
                units_or_currency="INR",
                extraction_confidence="high",
                is_management_statement=section["is_management_statement"],
                is_forecast=False,
                is_restated=False,
                scope_notes=scope,
                tags=section["tags"] + ["india", "bse"],
            ))

        logger.info("Extracted %d evidence records from %s", len(records), source_id)
        return records

    def _chunked_extract(
        self,
        text: str,
        source: SourceMetadata,
        scope: str | None,
    ) -> list[EvidenceRecord]:
        """Fall back to splitting text into manageable chunks."""
        records: list[EvidenceRecord] = []
        # Skip first 10% (usually headers/metadata)
        start = len(text) // 10
        remaining = text[start:]

        chunk_size = MAX_EXCERPT_LENGTH
        for i in range(0, min(len(remaining), chunk_size * 3), chunk_size):
            chunk = _clean_excerpt(remaining[i:i + chunk_size])
            if len(chunk) < 100:
                continue
            records.append(EvidenceRecord(
                evidence_id=f"ev_{_uid()}",
                source=source,
                excerpt=chunk,
                locator=f"Indian Filing — Chunk {len(records) + 1}",
                applicable_period=source.reporting_period,
                units_or_currency="INR",
                extraction_confidence="low",
                is_management_statement=False,
                tags=["general", "unstructured", "india"],
            ))

        return records
