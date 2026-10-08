"""Atomic claim model.

Every material statement the agent makes is represented as a typed claim
with evidence references, scope, and status.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from company_agent.domain.enums import ClaimStatus, ClaimType


@dataclass
class Claim:
    """An atomic, typed research claim.

    Claims must not blur categories — a sourced fact is different from
    an inference, which is different from an opinion.
    """

    claim_id: str
    claim_type: ClaimType
    statement: str                          # The atomic claim text
    scope: str                              # issuer/security/period this applies to
    time_period: str | None = None          # e.g. "FY2024", "Q3 2024"
    evidence_ids: list[str] = field(default_factory=list)
    calculation_id: str | None = None       # For calculated_result claims
    status: ClaimStatus = ClaimStatus.UNVERIFIED
    conflict_explanation: str | None = None  # If contested, explain why
    attribution: str | None = None           # For opinions: who said it
