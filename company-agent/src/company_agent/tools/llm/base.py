"""Abstract LLM provider interface.

One method per use case — not a generic "chat" method. This keeps
prompts and output structures well-defined and testable.

Two model tiers:
- light: cheap/fast model for planning and extraction (GPT-3.5-turbo → GPT-4o-mini later)
- heavy: powerful model for synthesis and thesis (GPT-3.5-turbo → GPT-4o later)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# --- Structured output types ---


@dataclass
class LLMResearchPlan:
    """Structured output from the research planning LLM call."""

    evidence_needs: list[dict[str, str]] = field(default_factory=list)
    # Each: {"category": ..., "reason": ..., "unanswered_question": ...}
    source_categories: list[str] = field(default_factory=list)
    extraction_queries: dict[str, str] = field(default_factory=dict)
    # Maps source type → what to extract from it
    notes: str | None = None


@dataclass
class LLMClaim:
    """A claim produced by the LLM synthesis step."""

    claim_type: str  # sourced_fact, inference, opinion
    statement: str
    evidence_ids: list[str] = field(default_factory=list)
    time_period: str | None = None


@dataclass
class LLMThesis:
    """Thesis produced by the LLM synthesis step."""

    hypothesis: str = ""
    bull_case: str = ""
    bear_case: str = ""
    assumptions: list[str] = field(default_factory=list)
    catalysts: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    validation_signals: list[str] = field(default_factory=list)
    invalidation_conditions: list[str] = field(default_factory=list)


@dataclass
class LLMCompanyOverview:
    """Company overview produced by the LLM synthesis step."""

    business_description: str = ""
    revenue_drivers: list[str] = field(default_factory=list)
    competitive_position: str = ""


@dataclass
class LLMSynthesisResult:
    """Complete output from the merged synthesis LLM call (Step 5+6)."""

    claims: list[LLMClaim] = field(default_factory=list)
    thesis: LLMThesis = field(default_factory=LLMThesis)
    company_overview: LLMCompanyOverview = field(default_factory=LLMCompanyOverview)
    limitations: list[str] = field(default_factory=list)


# --- Abstract interface ---


class LLMProvider(ABC):
    """Abstract LLM provider used by pipeline steps.

    Two methods, two LLM calls in the entire pipeline:
    - generate_research_plan: Step 2 (light model)
    - synthesize_research: Step 5+6 merged (heavy model)
    """

    @abstractmethod
    async def generate_research_plan(
        self,
        research_question: str,
        issuer_name: str,
        security_info: str,
        market_cap_info: str,
        period_scope: str,
        research_depth: str,
    ) -> LLMResearchPlan:
        """Generate a targeted research plan from the question.

        Uses the light model. Called in Step 2.
        """
        ...

    @abstractmethod
    async def synthesize_research(
        self,
        research_question: str,
        issuer_name: str,
        security_info: str,
        market_cap_info: str,
        period_scope: str,
        evidence_texts: list[dict[str, str]],
        # Each: {"evidence_id": ..., "source_title": ..., "excerpt": ..., "period": ..., "source_tier": ...}
    ) -> LLMSynthesisResult:
        """Synthesize claims, thesis, and company overview from evidence.

        Uses the heavy model. Called in merged Step 5+6.
        This is the one call that does all the reasoning.
        """
        ...
