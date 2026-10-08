"""Identity models for issuers, securities, and exchange listings.

The spec is clear: a company (issuer) is distinct from a tradable security.
One issuer can have multiple share classes, listings, or depositary receipts.
All research must preserve this distinction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class ExchangeListing:
    """Where a security trades."""

    exchange: str                    # e.g. "NASDAQ", "NYSE", "LSE"
    ticker: str                      # e.g. "GOOGL"
    currency: str                    # e.g. "USD"
    instrument_type: str = "common"  # common, adr, preferred, etc.


@dataclass(frozen=True)
class IssuerIdentity:
    """The company/business entity itself."""

    name: str                                   # e.g. "Alphabet Inc."
    identifiers: dict[str, str] = field(default_factory=dict)  # CIK, LEI, etc.
    country_of_incorporation: str | None = None
    prior_names: list[str] = field(default_factory=list)
    notes: str | None = None                    # mergers, name changes, etc.


@dataclass(frozen=True)
class SecurityIdentity:
    """A specific tradable instrument tied to an issuer."""

    issuer: IssuerIdentity
    listings: list[ExchangeListing] = field(default_factory=list)
    share_class: str | None = None      # e.g. "Class A", "Class C"
    isin: str | None = None
    cusip: str | None = None
    sedol: str | None = None


@dataclass
class IdentityResolution:
    """Result of the identity resolution step.

    Records what was matched, what alternatives were considered,
    the supporting source, confidence, and remaining uncertainty.
    """

    resolved_issuer: IssuerIdentity | None = None
    resolved_security: SecurityIdentity | None = None
    candidates_considered: list[str] = field(default_factory=list)
    resolution_source: str | None = None
    confidence: str = "unresolved"  # high, medium, low, unresolved
    unresolved_ambiguity: str | None = None
    as_of_date: date | None = None
