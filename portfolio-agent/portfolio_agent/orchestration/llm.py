"""LLM interface for the Portfolio Agent.

Two calls:
1. understand_and_plan — parse user query, classify intent, build execution plan
2. synthesize_answer — combine calculations + delegated results into user-facing answer

Uses OpenAI GPT-3.5-turbo by default. Same provider pattern as Company Agent.
"""

from __future__ import annotations

import json
import logging
import os

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# --- Prompt templates ---

UNDERSTAND_PLAN_SYSTEM = """You are a portfolio research assistant. Given a user's question and their portfolio holdings, you must:
1. Understand what the user is asking
2. Plan what actions are needed

Respond ONLY with valid JSON:
{
  "intent": "one of: portfolio_overview, exposure_analysis, company_research, fund_analysis, performance, concentration, comparison, general_question",
  "summary": "one sentence summary of what the user wants",
  "needs_calculation": true/false,
  "calculation_types": ["allocation", "exposure", "concentration"],
  "needs_company_research": true/false,
  "company_research_targets": [
    {"ticker": "RELIANCE", "name": "Reliance Industries", "question": "specific research question for this company"}
  ],
  "needs_fund_analysis": true/false,
  "fund_analysis_targets": [],
  "can_answer_directly": true/false,
  "direct_answer_reason": "if can_answer_directly, why no delegation needed"
}

Rules:
- If the question is about a specific company in the portfolio, set needs_company_research=true
- If the question is about the portfolio as a whole (allocation, exposure, top holdings), set needs_calculation=true
- If the question is general ("what do I own?"), needs_calculation=true with calculation_types=["allocation"]
- company_research_targets should only include companies in the user's portfolio
- For each company_research_targets, write a focused research_question that the Company Agent can answer"""

UNDERSTAND_PLAN_USER = """USER QUESTION: "{question}"

PORTFOLIO ({position_count} positions, invested: ₹{total_invested}):
{portfolio_summary}

What is the user asking, and what do we need to do?"""

SYNTHESIZE_SYSTEM = """You are a portfolio research analyst presenting findings to an investor.
Given the user's question, their portfolio, calculation results, and any company research, produce a clear answer.

Rules:
- Start with a direct answer to the question
- Cite specific numbers from calculations (don't make up numbers)
- Reference company research findings when relevant
- Mention limitations and data freshness
- Do NOT give buy/sell/hold advice
- Use INR (₹) for Indian market values
- Be concise but thorough

Respond with valid JSON:
{
  "answer": "the main answer in 2-4 paragraphs",
  "key_findings": ["finding 1", "finding 2"],
  "risks_and_limitations": ["limitation 1"],
  "follow_up_questions": ["suggested question 1"]
}"""

SYNTHESIZE_USER = """USER QUESTION: "{question}"

PORTFOLIO:
{portfolio_summary}

CALCULATION RESULTS:
{calculation_results}

COMPANY RESEARCH:
{research_results}

Synthesize a clear answer for the investor."""


class PortfolioLLM:
    """LLM provider for the Portfolio Agent."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._model = os.getenv("LLM_MODEL_PORTFOLIO", "gpt-3.5-turbo")

        if self._api_key:
            self._client = AsyncOpenAI(api_key=self._api_key)
        else:
            self._client = None

    @property
    def is_available(self) -> bool:
        return self._client is not None

    async def _call(self, system: str, user: str) -> dict:
        if not self._client:
            logger.warning("LLM not available — no API key")
            return {}

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return {}

    async def understand_and_plan(
        self,
        question: str,
        portfolio_summary: str,
        position_count: int,
        total_invested: float,
    ) -> dict:
        """LLM call #1 — understand intent and plan execution."""
        user_prompt = UNDERSTAND_PLAN_USER.format(
            question=question,
            portfolio_summary=portfolio_summary,
            position_count=position_count,
            total_invested=f"{total_invested:,.0f}",
        )
        result = await self._call(UNDERSTAND_PLAN_SYSTEM, user_prompt)

        # Fallback if LLM fails
        if not result:
            result = {
                "intent": "general_question",
                "summary": question,
                "needs_calculation": True,
                "calculation_types": ["allocation"],
                "needs_company_research": False,
                "company_research_targets": [],
                "needs_fund_analysis": False,
                "fund_analysis_targets": [],
                "can_answer_directly": False,
            }

        return result

    async def synthesize_answer(
        self,
        question: str,
        portfolio_summary: str,
        calculation_results: str,
        research_results: str,
    ) -> dict:
        """LLM call #2 — synthesize everything into user-facing answer."""
        user_prompt = SYNTHESIZE_USER.format(
            question=question,
            portfolio_summary=portfolio_summary,
            calculation_results=calculation_results or "No calculations performed.",
            research_results=research_results or "No company research performed.",
        )
        result = await self._call(SYNTHESIZE_SYSTEM, user_prompt)

        if not result:
            result = {
                "answer": f"I received your question: '{question}'. However, I couldn't generate a detailed analysis at this time. Please check that the OPENAI_API_KEY is configured.",
                "key_findings": [],
                "risks_and_limitations": ["LLM synthesis unavailable"],
                "follow_up_questions": [],
            }

        return result
