"""Atomic claim model."""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.domain.enums import ClaimStatus, ClaimType


@dataclass
class Claim:
    claim_id: str
    claim_type: ClaimType
    statement: str
    scope: str
    time_period: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    calculation_id: str | None = None
    status: ClaimStatus = ClaimStatus.UNVERIFIED
    conflict_explanation: str | None = None
    attribution: str | None = None
