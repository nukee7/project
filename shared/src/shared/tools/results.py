"""Result wrappers for shared tools."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConflictResult:
    conflicts_found: bool = False
    conflicts: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ClaimValidationResult:
    valid_claims: list[str] = field(default_factory=list)
    invalid_claims: list[str] = field(default_factory=list)
    issues: list[dict[str, str]] = field(default_factory=list)
