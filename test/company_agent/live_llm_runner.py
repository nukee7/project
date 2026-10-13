"""Live LLM test — real OpenAI + stub data sources. NOT production.

Run with:
    python -m test.company_agent.live_llm_runner
    OR: python -m company_agent --live
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import date

from company_agent.agent import CompanyAgent
from company_agent.contracts.request import AuthorizedSources, CompanyResearchRequest
from shared.domain.enums import InvocationContext, ResearchDepth
from test.company_agent.stubs import create_stub_registry


def _create_live_registry():
    from company_agent.tools.llm.openai_provider import OpenAILLMProvider
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set.")
        sys.exit(1)
    registry = create_stub_registry()
    registry.llm = OpenAILLMProvider(api_key=api_key)
    print(f"LLM: light={os.getenv('LLM_MODEL_LIGHT', 'gpt-3.5-turbo')}, heavy={os.getenv('LLM_MODEL_HEAVY', 'gpt-3.5-turbo')}")
    print("All other tools: stubs\n")
    return registry


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    print("=" * 70)
    print("  Company Agent — Live LLM Test")
    print("=" * 70)
    registry = _create_live_registry()
    request = CompanyResearchRequest(
        request_id="live-001", invocation_context=InvocationContext.DIRECT_POSITION,
        research_question="What are the key revenue drivers and competitive risks for this company over the last two fiscal years?",
        issuer_candidate="Alphabet Inc.", security_candidate="GOOGL", exchange_hint="NASDAQ",
        requested_as_of=date(2024, 12, 31), period_scope="FY2023-FY2024",
        authorized_sources=AuthorizedSources(), caller_context="Direct equity holding, reviewing annual thesis.",
        research_depth=ResearchDepth.STANDARD, market_cap_policy_version="v1.0",
    )
    agent = CompanyAgent(tools=registry)
    r = await agent.research(request)

    print(f"\nStatus:  {r.status.value}")
    print(f"Summary: {r.summary}")
    print(f"Claims:  {len(r.claims)}")
    if r.company_overview:
        print(f"\n--- Company Overview ---")
        print(f"  {r.company_overview.business_description}")
        for d in (r.company_overview.revenue_drivers or []):
            print(f"  - {d}")
    if r.claims:
        print(f"\n--- Claims ({len(r.claims)}) ---")
        for i, c in enumerate(r.claims, 1):
            print(f"  [{i}] ({c.claim_type.value}) {c.statement}")
    if r.thesis:
        t = r.thesis
        print(f"\n--- Thesis ---")
        print(f"  Hypothesis: {t.hypothesis}")
        print(f"  Bull: {t.bull_case}")
        print(f"  Bear: {t.bear_case}")
        for a in (t.assumptions or []):
            print(f"  Assumption: {a}")
        for c in (t.catalysts or []):
            print(f"  Catalyst: {c}")
        for rk in (t.risks or []):
            print(f"  Risk: {rk}")
    if r.trace_refs:
        print(f"\n--- Trace ({len(r.trace_refs)}) ---")
        for e in r.trace_refs:
            print(f"  {e}")


if __name__ == "__main__":
    asyncio.run(main())
