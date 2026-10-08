"""Evidence and source metadata models.

Every material research statement must trace back to a source record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from company_agent.domain.enums import SourceTier


@dataclass
class SourceMetadata:
    """Provenance metadata for a retrieved source."""

    source_id: str                          # Unique identifier for this source record
    publisher: str                          # e.g. "SEC EDGAR", "Company IR"
    title: str                              # Document title
    source_url: str | None = None           # URL or locator
    publication_date: date | None = None    # When the source was published
    reporting_period: str | None = None     # e.g. "FY2024", "Q3 2024"
    retrieval_time: datetime | None = None  # When we fetched it
    source_tier: SourceTier = SourceTier.SECONDARY_LICENSED
    licensing_notes: str | None = None      # Retention/usage constraints


@dataclass
class EvidenceRecord:
    """A single piece of extracted evidence tied to a source.

    The spec requires bounded records rather than document-level summaries.
    Each record preserves the exact excerpt, locator, period, units, and confidence.
    """

    evidence_id: str
    source: SourceMetadata
    excerpt: str                            # The exact supporting text or datum
    locator: str | None = None              # Page, section, table reference
    applicable_period: str | None = None    # The period this evidence covers
    units_or_currency: str | None = None    # e.g. "USD millions"
    extraction_confidence: str = "medium"   # high, medium, low
    is_management_statement: bool = False   # vs independently reported fact
    is_forecast: bool = False               # vs historical result
    is_restated: bool = False               # vs previously reported
    scope_notes: str | None = None          # company-wide vs segment, etc.
    tags: list[str] = field(default_factory=list)
