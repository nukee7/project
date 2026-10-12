"""Claim validation and conflict detection tool interfaces — shared across all agents."""

from __future__ import annotations

from abc import ABC, abstractmethod

from shared.domain.claims import Claim
from shared.domain.evidence import EvidenceRecord
from shared.tools.results import ClaimValidationResult, ConflictResult


class FindSourceConflicts(ABC):
    """Detect contradictory data for the same claim scope.

    Guardrail: Return conflicts rather than resolve them implicitly.
    """

    @abstractmethod
    async def find_conflicts(
        self,
        evidence_records: list[EvidenceRecord],
        scope: str | None = None,
    ) -> ConflictResult:
        ...


class ValidateClaims(ABC):
    """Check claim evidence/scope/freshness completeness.

    Guardrail: Cannot upgrade an unsupported claim to supported.
    """

    @abstractmethod
    async def validate(
        self,
        claims: list[Claim],
        evidence_records: list[EvidenceRecord],
    ) -> ClaimValidationResult:
        ...
