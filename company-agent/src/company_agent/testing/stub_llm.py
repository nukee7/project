"""Stub LLM provider — returns template responses without any API call.

Use this for development and testing without an OpenAI API key.
The pipeline runs end-to-end with predictable, structured output.
NOT for production use.
"""

from __future__ import annotations

from company_agent.tools.llm.base import (
    LLMClaim,
    LLMCompanyOverview,
    LLMProvider,
    LLMResearchPlan,
    LLMSynthesisResult,
    LLMThesis,
)


class StubLLMProvider(LLMProvider):
    """Returns deterministic template responses. No API key needed."""

    async def generate_research_plan(
        self,
        research_question: str,
        issuer_name: str,
        security_info: str,
        market_cap_info: str,
        period_scope: str,
        research_depth: str,
    ) -> LLMResearchPlan:
        return LLMResearchPlan(
            evidence_needs=[
                {
                    "category": "financial_reporting",
                    "reason": f"Core financials needed for: {research_question}",
                    "unanswered_question": f"What are the key financials for {period_scope}?",
                },
                {
                    "category": "business_and_revenue_drivers",
                    "reason": "Understand the company's business model",
                    "unanswered_question": "What drives revenue and growth?",
                },
                {
                    "category": "management_strategy_and_risks",
                    "reason": "Identify disclosed risks and strategy",
                    "unanswered_question": "What risks has management disclosed?",
                },
                {
                    "category": "competitive_context",
                    "reason": "Understand competitive positioning",
                    "unanswered_question": "What is the competitive landscape?",
                },
            ],
            source_categories=[
                "regulatory_filings",
                "earnings_releases",
                "earnings_transcripts",
            ],
            extraction_queries={
                "regulatory_filings": f"Extract key financials, risks, and business overview for {issuer_name}",
                "earnings_releases": f"Extract headline numbers and segment breakdown for {issuer_name}",
                "earnings_transcripts": f"Extract management commentary relevant to: {research_question}",
            },
            notes=f"[Stub plan] Research depth: {research_depth}. Question: {research_question}",
        )

    async def synthesize_research(
        self,
        research_question: str,
        issuer_name: str,
        security_info: str,
        market_cap_info: str,
        period_scope: str,
        evidence_texts: list[dict[str, str]],
    ) -> LLMSynthesisResult:
        ev_ids = [e.get("evidence_id", "unknown") for e in evidence_texts]

        return LLMSynthesisResult(
            claims=[
                LLMClaim(
                    claim_type="sourced_fact",
                    statement=f"[Stub] Key financial data for {issuer_name} extracted from {len(evidence_texts)} sources",
                    evidence_ids=ev_ids[:2],
                    time_period=period_scope,
                ),
                LLMClaim(
                    claim_type="sourced_fact",
                    statement=f"[Stub] Business model and revenue drivers identified for {issuer_name}",
                    evidence_ids=ev_ids[:1],
                    time_period=period_scope,
                ),
                LLMClaim(
                    claim_type="inference",
                    statement=f"[Stub] Based on available evidence, {issuer_name} operates in a competitive market with disclosed risk factors",
                    evidence_ids=ev_ids,
                    time_period=period_scope,
                ),
            ],
            thesis=LLMThesis(
                hypothesis=f"[Stub] {issuer_name} research hypothesis based on {len(evidence_texts)} evidence records across {period_scope}",
                bull_case=f"[Stub] Evidence-supported upside drivers for {issuer_name}",
                bear_case=f"[Stub] Credible downside risks for {issuer_name}",
                assumptions=[
                    f"Financial data for {period_scope} is materially complete",
                    "No material corporate events after the as-of date",
                    "Primary source filings have not been restated",
                ],
                catalysts=[
                    f"Next earnings release for {issuer_name}",
                    "Upcoming regulatory filings",
                ],
                risks=[
                    "Evidence may be stale relative to current conditions",
                    "Limited source coverage",
                ],
                validation_signals=[
                    f"Compare next quarter results against {period_scope} trends",
                    "Monitor for restatements",
                ],
                invalidation_conditions=[
                    "Material restatement of cited financial data",
                    "Corporate event that changes the issuer scope",
                ],
            ),
            company_overview=LLMCompanyOverview(
                business_description=f"[Stub] {issuer_name} is a company researched based on {len(evidence_texts)} evidence sources.",
                revenue_drivers=[f"[Stub] Primary revenue driver for {issuer_name}"],
                competitive_position=f"[Stub] Competitive position of {issuer_name} in its market",
            ),
            limitations=[
                "[Stub] Using stub LLM provider — no real analysis performed",
                "Replace with OpenAI provider for actual research synthesis",
            ],
        )
