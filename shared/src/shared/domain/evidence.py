"""Evidence and source metadata models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from shared.domain.enums import SourceTier


@dataclass
class SourceMetadata:
    source_id: str
    publisher: str
    title: str
    source_url: str | None = None
    publication_date: date | None = None
    reporting_period: str | None = None
    retrieval_time: datetime | None = None
    source_tier: SourceTier = SourceTier.SECONDARY_LICENSED
    licensing_notes: str | None = None


@dataclass
class EvidenceRecord:
    evidence_id: str
    source: SourceMetadata
    excerpt: str
    locator: str | None = None
    applicable_period: str | None = None
    units_or_currency: str | None = None
    extraction_confidence: str = "medium"
    is_management_statement: bool = False
    is_forecast: bool = False
    is_restated: bool = False
    scope_notes: str | None = None
    tags: list[str] = field(default_factory=list)
