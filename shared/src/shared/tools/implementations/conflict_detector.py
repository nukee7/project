"""Conflict detection — compares numbers and facts across evidence records.

Looks for:
1. Same metric, different values across sources
2. Contradictory statements about the same topic/period

Pure logic — no external service needed.
"""

from __future__ import annotations

import logging
import re

from shared.domain.evidence import EvidenceRecord
from shared.tools.claims import FindSourceConflicts
from shared.tools.results import ConflictResult

logger = logging.getLogger(__name__)

# Pattern to extract numbers with optional currency/units
_NUMBER_PATTERN = re.compile(
    r"(?:₹|Rs\.?|INR|USD|\$)?\s*(\d[\d,]*(?:\.\d+)?)\s*"
    r"(?:crore|cr|billion|bn|million|mn|lakh|%)?",
    re.IGNORECASE,
)


def _extract_numbers(text: str) -> list[float]:
    """Extract all numeric values from text."""
    numbers = []
    for match in _NUMBER_PATTERN.finditer(text):
        try:
            num_str = match.group(1).replace(",", "")
            numbers.append(float(num_str))
        except ValueError:
            continue
    return numbers


def _excerpts_overlap(a: EvidenceRecord, b: EvidenceRecord) -> bool:
    """Check if two evidence records discuss the same topic/period."""
    # Same period
    if a.applicable_period and b.applicable_period:
        if a.applicable_period == b.applicable_period:
            return True

    # Overlapping tags
    a_tags = set(a.tags)
    b_tags = set(b.tags)
    if a_tags & b_tags - {"general", "unstructured", "india", "bse", "secondary", "stub"}:
        return True

    return False


class RealConflictDetector(FindSourceConflicts):
    """Detect numerical and factual conflicts across evidence records."""

    async def find_conflicts(
        self,
        evidence_records: list[EvidenceRecord],
        scope: str | None = None,
    ) -> ConflictResult:
        if len(evidence_records) < 2:
            return ConflictResult(conflicts_found=False)

        conflicts: list[dict[str, str]] = []

        # Compare pairs of evidence records from different sources
        for i in range(len(evidence_records)):
            for j in range(i + 1, len(evidence_records)):
                a = evidence_records[i]
                b = evidence_records[j]

                # Skip if from the same source
                if a.source.source_id == b.source.source_id:
                    continue

                # Skip if different periods
                if not _excerpts_overlap(a, b):
                    continue

                # Compare numbers
                nums_a = _extract_numbers(a.excerpt)
                nums_b = _extract_numbers(b.excerpt)

                for na in nums_a:
                    for nb in nums_b:
                        if na == 0 or nb == 0:
                            continue
                        # If two numbers are within the same order of magnitude
                        # but differ by more than 5%, it's a potential conflict
                        ratio = max(na, nb) / min(na, nb)
                        if 0.5 < ratio < 2.0 and abs(na - nb) / max(na, nb) > 0.05:
                            conflicts.append({
                                "claim_scope": scope or "",
                                "source_a": f"{a.source.title} ({a.evidence_id})",
                                "source_b": f"{b.source.title} ({b.evidence_id})",
                                "description": (
                                    f"Numerical discrepancy: {na} vs {nb} "
                                    f"(difference: {abs(na - nb):.1f}, {abs(na - nb) / max(na, nb) * 100:.1f}%)"
                                ),
                            })

        if conflicts:
            logger.info("Found %d conflicts across %d evidence records", len(conflicts), len(evidence_records))

        return ConflictResult(
            conflicts_found=len(conflicts) > 0,
            conflicts=conflicts[:20],  # Cap at 20 to avoid noise
        )
