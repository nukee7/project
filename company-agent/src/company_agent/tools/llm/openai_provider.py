"""OpenAI LLM provider implementation.

Uses GPT-3.5-turbo by default (free tier). Switch to GPT-4o-mini / GPT-4o
later by changing the model names — same API call, same code.

Configuration via environment variables:
    OPENAI_API_KEY=sk-...
    LLM_MODEL_LIGHT=gpt-3.5-turbo     (for Step 2: planning)
    LLM_MODEL_HEAVY=gpt-3.5-turbo     (for Step 5: synthesis)
"""

from __future__ import annotations

import json
import logging
import os

from openai import AsyncOpenAI

from company_agent.tools.llm.base import (
    LLMClaim,
    LLMCompanyOverview,
    LLMProvider,
    LLMResearchPlan,
    LLMSynthesisResult,
    LLMThesis,
)

logger = logging.getLogger(__name__)

# --- Prompt templates ---

RESEARCH_PLAN_SYSTEM = """You are a research planning assistant for a company research agent.
Given a company and a research question, decide what evidence is needed and from which source types.
Respond ONLY with valid JSON matching this exact structure:
{
  "evidence_needs": [
    {"category": "...", "reason": "...", "unanswered_question": "..."}
  ],
  "source_categories": ["regulatory_filings", "earnings_releases", ...],
  "extraction_queries": {
    "regulatory_filings": "what to extract from filings",
    "earnings_releases": "what to extract from earnings"
  },
  "secondary_search_queries": [
    "targeted search query 1 for Google News",
    "targeted search query 2 for Google News"
  ],
  "notes": "any planning notes"
}
Rules:
- Keep evidence_needs focused on the question asked. Do not plan for topics the question doesn't cover.
- Source categories must be from: regulatory_filings, earnings_releases, earnings_transcripts, investor_presentations, secondary_reporting, analyst_opinion.
- secondary_search_queries are Google News search strings. Make them specific to the research question. Include the company name and keywords related to the question. Generate 2-4 targeted queries.
  Example: For "What are the competitive risks for Reliance?" generate queries like:
    "Reliance Industries competition threats market share"
    "Reliance Jio vs Airtel competitive pressure"
    "Reliance retail competition Amazon Flipkart"
  Do NOT generate generic queries like "Reliance Industries stock" or "Reliance news"."""

RESEARCH_PLAN_USER = """Company: {issuer_name} ({security_info})
Market cap: {market_cap_info}
Research question: "{research_question}"
Period: {period_scope}
Depth: {research_depth}

Generate a focused research plan."""

SYNTHESIS_SYSTEM = """You are a company research analyst. Analyze the evidence below and produce a structured research output.
Respond ONLY with valid JSON matching this exact structure:
{{
  "claims": [
    {{
      "claim_type": "sourced_fact|inference|opinion",
      "statement": "the claim text",
      "evidence_ids": ["ev_xxx"],
      "time_period": "FY2024"
    }}
  ],
  "thesis": {{
    "hypothesis": "one concise testable proposition",
    "bull_case": "evidence-supported upside (cite evidence IDs)",
    "bear_case": "evidence-supported downside (cite evidence IDs)",
    "assumptions": ["what must remain true"],
    "catalysts": ["upcoming events"],
    "risks": ["specific risks from evidence"],
    "validation_signals": ["what to monitor"],
    "invalidation_conditions": ["what would break the thesis"]
  }},
  "company_overview": {{
    "business_description": "what the company does",
    "revenue_drivers": ["key revenue sources"],
    "competitive_position": "market standing"
  }},
  "limitations": ["evidence gaps noticed"]
}}

Rules:
- Every sourced_fact must cite evidence_ids from the provided evidence
- Inferences must explain which evidence they derive from
- Do NOT do arithmetic — flag where calculations are needed
- Management forecasts are sourced_facts, not inferences
- Include counterevidence in bear_case
- Do NOT make buy/sell/hold recommendations"""

SYNTHESIS_USER = """COMPANY: {issuer_name} ({security_info})
MARKET CAP: {market_cap_info}
QUESTION: "{research_question}"
PERIOD: {period_scope}

EVIDENCE:
{evidence_block}

Analyze this evidence and produce the structured research output."""


class OpenAILLMProvider(LLMProvider):
    """OpenAI-backed LLM provider.

    Uses two model tiers:
    - light model for planning (default: gpt-3.5-turbo)
    - heavy model for synthesis (default: gpt-3.5-turbo)

    Switch to gpt-4o-mini / gpt-4o by setting environment variables.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_light: str | None = None,
        model_heavy: str | None = None,
        temperature: float = 0.1,
    ) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._model_light = model_light or os.getenv("LLM_MODEL_LIGHT", "gpt-3.5-turbo")
        self._model_heavy = model_heavy or os.getenv("LLM_MODEL_HEAVY", "gpt-3.5-turbo")
        self._temperature = temperature

        if not self._api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key to OpenAILLMProvider."
            )

        self._client = AsyncOpenAI(api_key=self._api_key)

    async def _call_llm(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> dict:
        """Make an LLM call and parse the JSON response."""
        logger.info("LLM call: model=%s, prompt_length=%d", model, len(user_prompt))

        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=self._temperature,
            )
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            raise

        content = response.choices[0].message.content or "{}"
        logger.info(
            "LLM response: model=%s, tokens_in=%s, tokens_out=%s",
            model,
            response.usage.prompt_tokens if response.usage else "?",
            response.usage.completion_tokens if response.usage else "?",
        )

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("LLM returned invalid JSON: %s", e)
            logger.debug("Raw content: %s", content[:500])
            return {}

    async def generate_research_plan(
        self,
        research_question: str,
        issuer_name: str,
        security_info: str,
        market_cap_info: str,
        period_scope: str,
        research_depth: str,
    ) -> LLMResearchPlan:
        """Generate research plan using the light model."""
        user_prompt = RESEARCH_PLAN_USER.format(
            issuer_name=issuer_name,
            security_info=security_info,
            market_cap_info=market_cap_info,
            research_question=research_question,
            period_scope=period_scope,
            research_depth=research_depth,
        )

        data = await self._call_llm(
            model=self._model_light,
            system_prompt=RESEARCH_PLAN_SYSTEM,
            user_prompt=user_prompt,
        )

        # Parse into structured output with fallbacks
        return LLMResearchPlan(
            evidence_needs=data.get("evidence_needs", []),
            source_categories=data.get("source_categories", [
                "regulatory_filings", "earnings_releases",
                "earnings_transcripts",
            ]),
            extraction_queries=data.get("extraction_queries", {}),
            secondary_search_queries=data.get("secondary_search_queries", []),
            notes=data.get("notes"),
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
        """Synthesize claims, thesis, and overview using the heavy model."""

        # Build the evidence block for the prompt
        evidence_lines: list[str] = []
        for ev in evidence_texts:
            ev_id = ev.get("evidence_id", "unknown")
            source = ev.get("source_title", "unknown source")
            excerpt = ev.get("excerpt", "")
            period = ev.get("period", "")
            tier = ev.get("source_tier", "")
            evidence_lines.append(
                f"[{ev_id}] Source: {source}\n"
                f"  \"{excerpt}\"\n"
                f"  Period: {period} | Tier: {tier}"
            )

        evidence_block = "\n\n".join(evidence_lines) if evidence_lines else "[No evidence available]"

        user_prompt = SYNTHESIS_USER.format(
            issuer_name=issuer_name,
            security_info=security_info,
            market_cap_info=market_cap_info,
            research_question=research_question,
            period_scope=period_scope,
            evidence_block=evidence_block,
        )

        data = await self._call_llm(
            model=self._model_heavy,
            system_prompt=SYNTHESIS_SYSTEM,
            user_prompt=user_prompt,
        )

        # Parse claims
        claims: list[LLMClaim] = []
        for c in data.get("claims", []):
            claims.append(LLMClaim(
                claim_type=c.get("claim_type", "sourced_fact"),
                statement=c.get("statement", ""),
                evidence_ids=c.get("evidence_ids", []),
                time_period=c.get("time_period"),
            ))

        # Parse thesis
        t = data.get("thesis", {})
        thesis = LLMThesis(
            hypothesis=t.get("hypothesis", ""),
            bull_case=t.get("bull_case", ""),
            bear_case=t.get("bear_case", ""),
            assumptions=t.get("assumptions", []),
            catalysts=t.get("catalysts", []),
            risks=t.get("risks", []),
            validation_signals=t.get("validation_signals", []),
            invalidation_conditions=t.get("invalidation_conditions", []),
        )

        # Parse company overview
        o = data.get("company_overview", {})
        overview = LLMCompanyOverview(
            business_description=o.get("business_description", ""),
            revenue_drivers=o.get("revenue_drivers", []),
            competitive_position=o.get("competitive_position", ""),
        )

        return LLMSynthesisResult(
            claims=claims,
            thesis=thesis,
            company_overview=overview,
            limitations=data.get("limitations", []),
        )
