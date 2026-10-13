"""SEC filing evidence extractor.

Parses the plain-text content of SEC filings (10-K, 10-Q) into
structured EvidenceRecord objects by identifying known sections.

10-K sections:
  Item 1    — Business
  Item 1A   — Risk Factors
  Item 7    — Management's Discussion and Analysis (MD&A)
  Item 7A   — Quantitative and Qualitative Disclosures About Market Risk
  Item 8    — Financial Statements

10-Q sections:
  Part I, Item 1  — Financial Statements
  Part I, Item 2  — MD&A
  Part I, Item 3  — Quantitative Disclosures
  Part II, Item 1 — Legal Proceedings
  Part II, Item 1A — Risk Factors

Each section becomes one or more EvidenceRecord objects with the
section name as the locator and relevant tags.
"""

from __future__ import annotations

import logging
import re
import uuid

from shared.domain.evidence import EvidenceRecord, SourceMetadata
from company_agent.tools.base import ExtractEvidence
from company_agent.tools.edgar.text_store import FilingTextStore

logger = logging.getLogger(__name__)

# Max chars per evidence record excerpt
MAX_EXCERPT_LENGTH = 3000


def _uid() -> str:
    return uuid.uuid4().hex[:12]


# Section patterns for 10-K filings
# These regex patterns match common headings in SEC filing text
_10K_SECTIONS = [
    {
        "name": "Business Overview",
        "pattern": r"(?:Item\s*1[\.\s]*(?:—|–|-|\.)\s*Business|ITEM\s*1[\.\s]*(?:—|–|-|\.)\s*BUSINESS)",
        "tags": ["business", "overview", "products", "revenue_drivers"],
        "is_management_statement": False,
    },
    {
        "name": "Risk Factors",
        "pattern": r"(?:Item\s*1A[\.\s]*(?:—|–|-|\.)\s*Risk\s*Factors|ITEM\s*1A[\.\s]*(?:—|–|-|\.)\s*RISK\s*FACTORS)",
        "tags": ["risks", "risk_factors"],
        "is_management_statement": True,
    },
    {
        "name": "MD&A",
        "pattern": r"(?:Item\s*7[\.\s]*(?:—|–|-|\.)\s*Management|ITEM\s*7[\.\s]*(?:—|–|-|\.)\s*MANAGEMENT)",
        "tags": ["mda", "financial_analysis", "revenue", "expenses", "results"],
        "is_management_statement": True,
    },
    {
        "name": "Market Risk Disclosures",
        "pattern": r"(?:Item\s*7A[\.\s]*(?:—|–|-|\.)\s*Quantitative|ITEM\s*7A[\.\s]*(?:—|–|-|\.)\s*QUANTITATIVE)",
        "tags": ["market_risk", "quantitative"],
        "is_management_statement": True,
    },
]

# Section patterns for 10-Q filings
_10Q_SECTIONS = [
    {
        "name": "MD&A (Quarterly)",
        "pattern": r"(?:Item\s*2[\.\s]*(?:—|–|-|\.)\s*Management|ITEM\s*2[\.\s]*(?:—|–|-|\.)\s*MANAGEMENT)",
        "tags": ["mda", "quarterly", "financial_analysis", "revenue"],
        "is_management_statement": True,
    },
    {
        "name": "Risk Factors (Quarterly)",
        "pattern": r"(?:Item\s*1A[\.\s]*(?:—|–|-|\.)\s*Risk\s*Factors|ITEM\s*1A[\.\s]*(?:—|–|-|\.)\s*RISK\s*FACTORS)",
        "tags": ["risks", "risk_factors", "quarterly"],
        "is_management_statement": True,
    },
]


def _detect_filing_type(text: str) -> str:
    """Detect whether this is a 10-K or 10-Q from the text content."""
    text_upper = text[:5000].upper()
    if "ANNUAL REPORT" in text_upper or "FORM 10-K" in text_upper:
        return "10-K"
    if "QUARTERLY REPORT" in text_upper or "FORM 10-Q" in text_upper:
        return "10-Q"
    # Check source_id pattern
    return "unknown"


def _find_sections(
    text: str,
    section_defs: list[dict],
) -> list[dict]:
    """Find section boundaries in the filing text.

    Returns list of {"name", "start", "end", "tags", "is_management_statement"}.
    """
    matches: list[dict] = []

    for sec_def in section_defs:
        pattern = sec_def["pattern"]
        for m in re.finditer(pattern, text, re.IGNORECASE):
            matches.append({
                "name": sec_def["name"],
                "start": m.start(),
                "tags": sec_def["tags"],
                "is_management_statement": sec_def["is_management_statement"],
            })

    # Sort by position in document
    matches.sort(key=lambda x: x["start"])

    # Set end positions (each section ends where the next one starts)
    for i in range(len(matches)):
        if i + 1 < len(matches):
            matches[i]["end"] = matches[i + 1]["start"]
        else:
            matches[i]["end"] = len(text)

    return matches


def _clean_excerpt(text: str) -> str:
    """Clean up an excerpt: collapse whitespace, trim."""
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text


class EdgarExtractEvidence(ExtractEvidence):
    """Extract structured evidence records from SEC filing text.

    Reads filing text from the shared FilingTextStore, identifies
    known sections (Business, Risk Factors, MD&A, etc.), and creates
    EvidenceRecord objects for each section.

    Each section excerpt is trimmed to MAX_EXCERPT_LENGTH chars to
    keep evidence records manageable for downstream LLM processing.
    """

    def __init__(self, text_store: FilingTextStore) -> None:
        self._text_store = text_store

    async def extract(
        self,
        source: SourceMetadata,
        extraction_query: str,
        scope: str | None = None,
    ) -> list[EvidenceRecord]:
        """Extract evidence records from a retrieved filing."""
        source_id = source.source_id
        text = self._text_store.get(source_id)

        if not text:
            logger.warning("No cached text for source %s — skipping extraction", source_id)
            return []

        logger.info(
            "Extracting evidence from %s (%d chars), query='%s'",
            source_id, len(text), extraction_query[:80],
        )

        # Detect filing type and choose section patterns
        filing_type = _detect_filing_type(text)
        if filing_type == "10-K":
            section_defs = _10K_SECTIONS
        elif filing_type == "10-Q":
            section_defs = _10Q_SECTIONS
        else:
            # Try both
            section_defs = _10K_SECTIONS + _10Q_SECTIONS

        logger.info("Detected filing type: %s", filing_type)

        # Find sections in the text
        sections = _find_sections(text, section_defs)

        if not sections:
            # No known sections found — extract a chunk from the middle
            # (skip the XBRL header at the start)
            logger.info("No known sections found — extracting general content")
            midpoint = len(text) // 4  # Skip the first quarter (usually XBRL/headers)
            chunk = text[midpoint : midpoint + MAX_EXCERPT_LENGTH]
            if chunk.strip():
                return [
                    EvidenceRecord(
                        evidence_id=f"ev_{_uid()}",
                        source=source,
                        excerpt=_clean_excerpt(chunk),
                        locator="General content (no section headers detected)",
                        applicable_period=source.reporting_period,
                        extraction_confidence="low",
                        is_management_statement=False,
                        tags=["general", "unstructured"],
                    )
                ]
            return []

        # Create an EvidenceRecord for each section
        records: list[EvidenceRecord] = []
        for section in sections:
            section_text = text[section["start"] : section["end"]]
            excerpt = _clean_excerpt(section_text)

            if len(excerpt) < 50:
                # Section too short — skip
                continue

            # Truncate long sections
            if len(excerpt) > MAX_EXCERPT_LENGTH:
                excerpt = excerpt[:MAX_EXCERPT_LENGTH] + " [TRUNCATED]"

            record = EvidenceRecord(
                evidence_id=f"ev_{_uid()}",
                source=source,
                excerpt=excerpt,
                locator=f"{filing_type} — {section['name']}",
                applicable_period=source.reporting_period,
                units_or_currency="USD",
                extraction_confidence="high" if filing_type != "unknown" else "medium",
                is_management_statement=section["is_management_statement"],
                is_forecast=False,
                is_restated=False,
                scope_notes=scope,
                tags=section["tags"] + [filing_type],
            )
            records.append(record)

        logger.info(
            "Extracted %d evidence records from %s (%s)",
            len(records), source_id, filing_type,
        )

        return records
