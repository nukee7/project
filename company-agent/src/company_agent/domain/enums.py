"""Enumerations used across the Company Agent domain."""

from enum import Enum


class InvocationContext(str, Enum):
    """Why the Company Agent was called."""

    DIRECT_POSITION = "direct_position"
    FUND_UNDERLYING = "fund_underlying"
    STANDALONE_RESEARCH = "standalone_research"


class ResearchDepth(str, Enum):
    """Controls source breadth and analysis depth."""

    SCREEN = "screen"
    STANDARD = "standard"
    DEEP = "deep"


class SourceTier(str, Enum):
    """Evidence source hierarchy, from most authoritative to least."""

    PRIMARY_FILING = "primary_filing"          # Regulatory filings, audited statements
    PRIMARY_ISSUER = "primary_issuer"          # Earnings releases, transcripts, presentations
    OFFICIAL_NOTICE = "official_notice"        # Exchange/regulator notices
    SECONDARY_LICENSED = "secondary_licensed"  # Licensed reputable reporting
    OPINION = "opinion"                        # Analyst/opinion material


class ClaimType(str, Enum):
    """Classification of every atomic claim the agent produces."""

    SOURCED_FACT = "sourced_fact"          # Directly supported by an appropriate source
    CALCULATED_RESULT = "calculated_result"  # Returned by an approved deterministic service
    INFERENCE = "inference"                # Reasoned interpretation tied to evidence
    OPINION = "opinion"                    # Clearly attributed, non-factual assessment


class ClaimStatus(str, Enum):
    """Current state of a claim's evidence support."""

    SUPPORTED = "supported"
    CONTESTED = "contested"
    STALE = "stale"
    SUPERSEDED = "superseded"
    UNVERIFIED = "unverified"
    NEEDS_REVIEW = "needs_review"


class MarketCapClassification(str, Enum):
    """Size classification based on market capitalization."""

    SMALL_CAP = "small_cap"
    MID_CAP = "mid_cap"
    LARGE_CAP = "large_cap"
    UNKNOWN = "unknown"


class WorkProductStatus(str, Enum):
    """Overall status of the agent's work product."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    NEEDS_REVIEW = "needs_review"
