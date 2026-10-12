"""Identity models for issuers, securities, and exchange listings."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class ExchangeListing:
    exchange: str
    ticker: str
    currency: str
    instrument_type: str = "common"


@dataclass(frozen=True)
class IssuerIdentity:
    name: str
    identifiers: dict[str, str] = field(default_factory=dict)
    country_of_incorporation: str | None = None
    prior_names: list[str] = field(default_factory=list)
    notes: str | None = None


@dataclass(frozen=True)
class SecurityIdentity:
    issuer: IssuerIdentity
    listings: list[ExchangeListing] = field(default_factory=list)
    share_class: str | None = None
    isin: str | None = None
    cusip: str | None = None
    sedol: str | None = None


@dataclass
class IdentityResolution:
    resolved_issuer: IssuerIdentity | None = None
    resolved_security: SecurityIdentity | None = None
    candidates_considered: list[str] = field(default_factory=list)
    resolution_source: str | None = None
    confidence: str = "unresolved"
    unresolved_ambiguity: str | None = None
    as_of_date: date | None = None
