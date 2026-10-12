"""Live LLM test runner for the Company Agent.

Runs the pipeline with REAL OpenAI LLM calls + stub tools for data sources.
This lets you see actual LLM-generated research plans, claims, and thesis
without needing real SEC EDGAR or market data integrations.

Requires: OPENAI_API_KEY environment variable.

Run with:
    python -m company_agent --live
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from dataclasses import asdict
from datetime import date
from enum import Enum

from company_agent.agent import CompanyAgent
from company_agent.contracts.request import (
    AuthorizedSources,
    CompanyResearchRequest,
)
from shared.domain.enums import InvocationContext, ResearchDepth
from company_agent.testing.stubs import create_stub_registry


class _EnhancedEncoder(json.JSONEncoder):
    def default(self, o: object) -> object:
        if isinstance(o, Enum):
            return o.value
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return super().default(o)


def _to_json(obj: object) -> str:
    return json.dumps(asdict(obj), indent=2, cls=_EnhancedEncoder, default=str)


def _create_live_registry():
    """Create a registry with real OpenAI LLM + stub everything else."""
    from company_agent.tools.llm.openai_provider import OpenAILLMProvider

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable is not set.")
        print("Set it with: set OPENAI_API_KEY=sk-your-key-here")
        sys.exit(1)

    # Start with all stubs
    registry = create_stub_registry()

    # Replace LLM with real OpenAI
    registry.llm = OpenAILLMProvider(api_key=api_key)

    model_light = os.getenv("LLM_MODEL_LIGHT", "gpt-3.5-turbo")
    model_heavy = os.getenv("LLM_MODEL_HEAVY", "gpt-3.5-turbo")
    print(f"LLM models: light={model_light}, heavy={model_heavy}")
    print(f"All other tools: stubs (fake data)\n")

    return registry


async def run_live_example(
    name: str,
    request: CompanyResearchRequest,
    registry,
) -> None:
    """Run a single example with real LLM and print results."""
    print(f"\n{'='*70}")
    print(f"  LIVE LLM TEST: {name}")
    print(f"{'='*70}\n")

    agent = CompanyAgent(tools=registry)
    response = await agent.research(request)

    # --- Summary ---
    print(f"Status:  {response.status.value}")
    print(f"Summary: {response.summary}")
    print(f"Claims:  {len(response.claims)}")
    print(f"Sources: {response.evidence_summary.source_count if response.evidence_summary else 0}")
    if response.processing_time_seconds:
        print(f"Time:    {response.processing_time_seconds:.2f}s")

    if response.identity and response.identity.resolution.resolved_issuer:
        print(f"Issuer:  {response.identity.resolution.resolved_issuer.name}")

    if response.market_cap_classification:
        mc = response.market_cap_classification
        print(f"MktCap:  {mc.classification.value} ({mc.market_cap_value} {mc.currency})")

    # --- Company Overview (LLM-generated) ---
    if response.company_overview:
        co = response.company_overview
        print(f"\n--- Company Overview (LLM) ---")
        print(f"  Description: {co.business_description}")
        if co.revenue_drivers:
            print(f"  Revenue drivers:")
            for rd in co.revenue_drivers:
                print(f"    - {rd}")
        if co.competitive_position:
            print(f"  Competitive position: {co.competitive_position}")

    # --- Claims (LLM-generated) ---
    if response.claims:
        print(f"\n--- Claims ({len(response.claims)}) ---")
        for i, claim in enumerate(response.claims, 1):
            print(f"  [{i}] ({claim.claim_type.value}) {claim.statement}")
            if claim.evidence_ids:
                print(f"      Evidence: {', '.join(claim.evidence_ids)}")

    # --- Thesis (LLM-generated) ---
    if response.thesis:
        t = response.thesis
        print(f"\n--- Thesis (LLM) ---")
        print(f"  Hypothesis: {t.hypothesis}")
        print(f"\n  Bull case: {t.bull_case}")
        print(f"\n  Bear case: {t.bear_case}")
        if t.assumptions:
            print(f"\n  Assumptions:")
            for a in t.assumptions:
                print(f"    - {a}")
        if t.catalysts:
            print(f"\n  Catalysts:")
            for c in t.catalysts:
                print(f"    - {c}")
        if t.risks:
            print(f"\n  Risks:")
            for r in t.risks:
                print(f"    - {r}")
        if t.invalidation_conditions:
            print(f"\n  Invalidation conditions:")
            for ic in t.invalidation_conditions:
                print(f"    - {ic}")

    # --- Limitations ---
    if response.limitations and response.limitations.evidence_gaps:
        print(f"\n--- Limitations ({len(response.limitations.evidence_gaps)}) ---")
        for gap in response.limitations.evidence_gaps:
            print(f"  - {gap}")

    # --- Trace ---
    if response.trace_refs:
        print(f"\n--- Trace ({len(response.trace_refs)} entries) ---")
        for entry in response.trace_refs:
            print(f"  {entry}")


async def main() -> None:
    """Run live LLM test with one example request."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    print("=" * 70)
    print("  Company Agent — Live LLM Test")
    print("  Real OpenAI calls + stub data sources")
    print("=" * 70)

    registry = _create_live_registry()

    # Run one focused example to see real LLM output
    request = CompanyResearchRequest(
        request_id="live-001",
        invocation_context=InvocationContext.DIRECT_POSITION,
        research_question=(
            "What are the key revenue drivers and competitive risks "
            "for this company over the last two fiscal years?"
        ),
        issuer_candidate="Alphabet Inc.",
        security_candidate="GOOGL",
        exchange_hint="NASDAQ",
        requested_as_of=date(2024, 12, 31),
        period_scope="FY2023-FY2024",
        authorized_sources=AuthorizedSources(),
        caller_context="Direct equity holding in portfolio, reviewing annual thesis.",
        research_depth=ResearchDepth.STANDARD,
        market_cap_policy_version="v1.0",
    )

    await run_live_example(
        "Alphabet Inc. (GOOGL) — Revenue Drivers & Competitive Risks",
        request,
        registry,
    )


if __name__ == "__main__":
    asyncio.run(main())
