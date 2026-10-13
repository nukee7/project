"""Test runner with stub tools. NOT production code.

Run with:
    python -m test.company_agent.example_runner
    OR: python -m company_agent --test
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from company_agent.agent import CompanyAgent
from company_agent.contracts.request import AuthorizedSources, CompanyResearchRequest
from shared.domain.enums import InvocationContext, ResearchDepth
from test.company_agent.stubs import create_stub_registry


def _example_direct_position():
    return CompanyResearchRequest(
        request_id="req-001", invocation_context=InvocationContext.DIRECT_POSITION,
        research_question="What are the key revenue drivers and competitive risks for this company over the last two fiscal years?",
        issuer_candidate="Alphabet Inc.", security_candidate="GOOGL", exchange_hint="NASDAQ",
        requested_as_of=date(2024, 12, 31), period_scope="FY2023-FY2024",
        authorized_sources=AuthorizedSources(), caller_context="Direct equity holding, reviewing annual thesis.",
        research_depth=ResearchDepth.STANDARD, market_cap_policy_version="v1.0",
    )


def _example_fund_underlying():
    return CompanyResearchRequest(
        request_id="req-002", invocation_context=InvocationContext.FUND_UNDERLYING,
        research_question="Provide a company research brief for this fund holding to assess concentration risk.",
        issuer_candidate="NVIDIA Corporation", security_candidate="NVDA", exchange_hint="NASDAQ",
        requested_as_of=date(2024, 9, 30), period_scope="FY2024",
        authorized_sources=AuthorizedSources(), caller_context="Top-5 holding in Vanguard Growth Index Fund, weight 8.2%.",
        research_depth=ResearchDepth.STANDARD, market_cap_policy_version="v1.0",
        fund_holding_date=date(2024, 9, 30), fund_identifier="VIGAX", fund_share_class="Admiral",
    )


def _example_invalid():
    return CompanyResearchRequest(
        request_id="", invocation_context=InvocationContext.FUND_UNDERLYING,
        research_question="", issuer_candidate="", requested_as_of=date(2024, 12, 31),
        period_scope="", authorized_sources=AuthorizedSources(), caller_context="",
        research_depth=ResearchDepth.SCREEN, market_cap_policy_version="",
    )


async def run_example(name, request):
    print(f"\n{'='*70}\n  EXAMPLE: {name}\n{'='*70}\n")
    agent = CompanyAgent(tools=create_stub_registry())
    r = await agent.research(request)
    print(f"Status:  {r.status.value}")
    print(f"Summary: {r.summary}")
    print(f"Claims:  {len(r.claims)}")
    print(f"Sources: {r.evidence_summary.source_count if r.evidence_summary else 0}")
    if r.processing_time_seconds:
        print(f"Time:    {r.processing_time_seconds:.2f}s")
    if r.identity and r.identity.resolution.resolved_issuer:
        print(f"Issuer:  {r.identity.resolution.resolved_issuer.name}")
    if r.market_cap_classification:
        mc = r.market_cap_classification
        print(f"MktCap:  {mc.classification.value} ({mc.market_cap_value} {mc.currency})")
    if r.thesis:
        print(f"\nThesis: {r.thesis.hypothesis[:120]}...")
    if r.limitations and r.limitations.evidence_gaps:
        print(f"\nLimitations ({len(r.limitations.evidence_gaps)}):")
        for g in r.limitations.evidence_gaps:
            print(f"  - {g}")
    if r.open_questions:
        print(f"\nOpen questions ({len(r.open_questions)}):")
        for q in r.open_questions:
            print(f"  - {q}")
    if r.trace_refs:
        print(f"\nTrace ({len(r.trace_refs)} entries):")
        for e in r.trace_refs:
            print(f"  {e}")


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    await run_example("Direct Position — Alphabet (GOOGL)", _example_direct_position())
    await run_example("Fund Underlying — NVIDIA (NVDA) via VIGAX", _example_fund_underlying())
    await run_example("Invalid Request (should fail validation)", _example_invalid())


if __name__ == "__main__":
    asyncio.run(main())
