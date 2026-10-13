"""Stub LLM provider — template responses, no API calls. NOT for production."""

from __future__ import annotations

from company_agent.tools.llm.base import (
    LLMClaim, LLMCompanyOverview, LLMProvider,
    LLMResearchPlan, LLMSynthesisResult, LLMThesis,
)


class StubLLMProvider(LLMProvider):

    async def generate_research_plan(self, research_question, issuer_name, security_info, market_cap_info, period_scope, research_depth):
        return LLMResearchPlan(
            evidence_needs=[
                {"category": "financial_reporting", "reason": f"Core financials for: {research_question}", "unanswered_question": f"Key financials for {period_scope}?"},
                {"category": "business_and_revenue_drivers", "reason": "Business model", "unanswered_question": "What drives revenue?"},
                {"category": "management_strategy_and_risks", "reason": "Disclosed risks", "unanswered_question": "What risks disclosed?"},
                {"category": "competitive_context", "reason": "Competitive positioning", "unanswered_question": "Competitive landscape?"},
            ],
            source_categories=["regulatory_filings", "earnings_releases", "earnings_transcripts"],
            extraction_queries={
                "regulatory_filings": f"Extract financials, risks, overview for {issuer_name}",
                "earnings_releases": f"Extract headline numbers for {issuer_name}",
                "earnings_transcripts": f"Extract management commentary for: {research_question}",
            },
            notes=f"[Stub plan] Depth: {research_depth}. Question: {research_question}",
        )

    async def synthesize_research(self, research_question, issuer_name, security_info, market_cap_info, period_scope, evidence_texts):
        ev_ids = [e.get("evidence_id", "unknown") for e in evidence_texts]
        return LLMSynthesisResult(
            claims=[
                LLMClaim(claim_type="sourced_fact", statement=f"[Stub] Key financial data for {issuer_name} from {len(evidence_texts)} sources", evidence_ids=ev_ids[:2], time_period=period_scope),
                LLMClaim(claim_type="sourced_fact", statement=f"[Stub] Business model and revenue drivers for {issuer_name}", evidence_ids=ev_ids[:1], time_period=period_scope),
                LLMClaim(claim_type="inference", statement=f"[Stub] {issuer_name} operates in competitive market with disclosed risks", evidence_ids=ev_ids, time_period=period_scope),
            ],
            thesis=LLMThesis(
                hypothesis=f"[Stub] {issuer_name} hypothesis based on {len(evidence_texts)} records across {period_scope}",
                bull_case=f"[Stub] Upside drivers for {issuer_name}",
                bear_case=f"[Stub] Downside risks for {issuer_name}",
                assumptions=[f"Financial data for {period_scope} is complete", "No material events after as-of date", "Filings not restated"],
                catalysts=[f"Next earnings for {issuer_name}", "Upcoming filings"],
                risks=["Evidence may be stale", "Limited coverage"],
                validation_signals=[f"Compare next quarter against {period_scope}", "Monitor restatements"],
                invalidation_conditions=["Material restatement", "Corporate event changes scope"],
            ),
            company_overview=LLMCompanyOverview(
                business_description=f"[Stub] {issuer_name} researched from {len(evidence_texts)} sources.",
                revenue_drivers=[f"[Stub] Primary revenue driver for {issuer_name}"],
                competitive_position=f"[Stub] Competitive position of {issuer_name}",
            ),
            limitations=["[Stub] Using stub LLM — no real analysis", "Replace with OpenAI for real synthesis"],
        )
