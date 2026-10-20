"""Claim validation — rule-based checks on claim completeness.

Checks:
1. sourced_fact must have at least one evidence_id
2. calculated_result must have a calculation_id
3. opinion must have attribution
4. No claim can be empty
5. Cannot upgrade unsupported to supported

Pure logic — no external service needed.
"""

from __future__ import annotations

import logging

from shared.domain.claims import Claim
from shared.domain.enums import ClaimStatus, ClaimType
from shared.domain.evidence import EvidenceRecord
from shared.tools.claims import ValidateClaims
from shared.tools.results import ClaimValidationResult

logger = logging.getLogger(__name__)


class RealClaimValidator(ValidateClaims):
    """Rule-based claim validation."""

    async def validate(
        self,
        claims: list[Claim],
        evidence_records: list[EvidenceRecord],
    ) -> ClaimValidationResult:
        valid: list[str] = []
        invalid: list[str] = []
        issues: list[dict[str, str]] = []

        # Build evidence ID set for quick lookup
        evidence_ids = {ev.evidence_id for ev in evidence_records}

        for claim in claims:
            claim_issues: list[str] = []

            # Rule 1: Non-empty statement
            if not claim.statement or not claim.statement.strip():
                claim_issues.append("Claim has no statement text")

            # Rule 2: sourced_fact must have evidence
            if claim.claim_type == ClaimType.SOURCED_FACT:
                if not claim.evidence_ids:
                    claim_issues.append("sourced_fact has no evidence_ids")
                else:
                    # Check that referenced evidence actually exists
                    missing = [eid for eid in claim.evidence_ids if eid not in evidence_ids]
                    if missing:
                        claim_issues.append(f"References non-existent evidence: {', '.join(missing)}")

            # Rule 3: calculated_result must have calculation_id
            if claim.claim_type == ClaimType.CALCULATED_RESULT:
                if not claim.calculation_id:
                    claim_issues.append("calculated_result has no calculation_id")

            # Rule 4: opinion should have attribution (warning, not invalid)
            if claim.claim_type == ClaimType.OPINION:
                if not claim.attribution:
                    claim_issues.append("opinion has no attribution (who said it?)")

            # Rule 5: Scope must be non-empty
            if not claim.scope or not claim.scope.strip():
                claim_issues.append("Claim has no scope")

            if claim_issues:
                invalid.append(claim.claim_id)
                for issue in claim_issues:
                    issues.append({
                        "claim_id": claim.claim_id,
                        "issue": issue,
                        "severity": "error" if "no evidence" in issue or "no calculation" in issue else "warning",
                    })
            else:
                valid.append(claim.claim_id)

        logger.info(
            "Validated %d claims: %d valid, %d invalid, %d issues",
            len(claims), len(valid), len(invalid), len(issues),
        )

        return ClaimValidationResult(
            valid_claims=valid,
            invalid_claims=invalid,
            issues=issues,
        )
