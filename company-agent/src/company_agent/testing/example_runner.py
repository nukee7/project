"""Example runner for the Company Agent.

Demonstrates end-to-end usage with stub tools.
NOT production code — this is for development and testing only.

Run with:
  python -m company_agent.testing.example_runner
"""

from __future__ import annotations

import asyncio
import json
import logging
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


# --- JSON serialization helper ---


class _EnhancedEncoder(json.JSONEncoder):
    """Handle date, datetime, and Enum serialization."""

    def default(self, o: object) -> object:
        if isinstance(o, Enum):
            return o.value
        if hasattr(o, "isoformat"):
            return o.isoformat()  # type: ignore[union-attr]
        return super().default(o)


def _to_json(obj: object) -> str:
    """Convert a dataclass to pretty-printed JSON."""
    return json.dumps(asdict(obj), indent=2, cls=_EnhancedEncoder, default=str)  # type: ignore[call-overload]


# --- Example requests ---


def _example_direct_position_request() -> CompanyResearchRequest:
    """Simulate a Portfolio Agent asking about a direct stock holding."""
    return CompanyResearchRequest(
        request_id="req-001",
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


def _example_fund_underlying_request() -> CompanyResearchRequest:
    """Simulate a Mutual Fund Agent asking about a fund holding."""
    return CompanyResearchRequest(
        request_id="req-002",
        invocation_context=InvocationContext.FUND_UNDERLYING,
        research_question=(
            "Provide a company research brief for this fund holding "
            "to assess its contribution to fund concentration risk."
        ),
        issuer_candidate="NVIDIA Corporation",
        security_candidate="NVDA",
        exchange_hint="NASDAQ",
        requested_as_of=date(2024, 9, 30),
        period_scope="FY2024",
        authorized_sources=AuthorizedSources(),
        caller_context="Top-5 holding in Vanguard Growth Index Fund, weight 8.2%.",
        research_depth=ResearchDepth.STANDARD,
        market_cap_policy_version="v1.0",
        fund_holding_date=date(2024, 9, 30),
        fund_identifier="VIGAX",
        fund_share_class="Admiral",
    )


def _example_invalid_request() -> CompanyResearchRequest:
    """Demonstrate validation failure."""
    return CompanyResearchRequest(
        request_id="",
        invocation_context=InvocationContext.FUND_UNDERLYING,
        research_question="",
        issuer_candidate="",
        requested_as_of=date(2024, 12, 31),
        period_scope="",
        authorized_sources=AuthorizedSources(),
        caller_context="",
        research_depth=ResearchDepth.SCREEN,
        market_cap_policy_version="",
    )


# --- Main ---


async def run_example(name: str, request: CompanyResearchRequest) -> None:
    """Run a single example and print results."""
    print(f"\n{'='*70}")
    print(f"  EXAMPLE: {name}")
    print(f"{'='*70}\n")

    agent = CompanyAgent(tools=create_stub_registry())
    response = await agent.research(request)

    print(f"Status:  {response.status.value}")
    print(f"Summary: {response.summary}")
    print(f"Claims:  {len(response.claims)}")
    print(f"Sources: {response.evidence_summary.source_count if response.evidence_summary else 0}")
    print(f"Time:    {response.processing_time_seconds:.2f}s" if response.processing_time_seconds else "")

    if response.identity and response.identity.resolution.resolved_issuer:
        print(f"Issuer:  {response.identity.resolution.resolved_issuer.name}")

    if response.market_cap_classification:
        mc = response.market_cap_classification
        print(f"MktCap:  {mc.classification.value} ({mc.market_cap_value} {mc.currency})")

    if response.thesis:
        print(f"\nThesis: {response.thesis.hypothesis[:120]}...")
        print(f"  Assumptions:  {len(response.thesis.assumptions)}")
        print(f"  Catalysts:    {len(response.thesis.catalysts)}")
        print(f"  Risks:        {len(response.thesis.risks)}")

    if response.limitations and response.limitations.evidence_gaps:
        print(f"\nLimitations ({len(response.limitations.evidence_gaps)}):")
        for gap in response.limitations.evidence_gaps:
            print(f"  - {gap}")

    if response.open_questions:
        print(f"\nOpen questions ({len(response.open_questions)}):")
        for q in response.open_questions:
            print(f"  - {q}")

    if response.trace_refs:
        print(f"\nTrace log ({len(response.trace_refs)} entries):")
        for entry in response.trace_refs:
            print(f"  {entry}")


async def main() -> None:
    """Run all examples."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    await run_example(
        "Direct Position — Alphabet Inc. (GOOGL)",
        _example_direct_position_request(),
    )
    await run_example(
        "Fund Underlying — NVIDIA (NVDA) via VIGAX",
        _example_fund_underlying_request(),
    )
    await run_example(
        "Invalid Request (should fail validation)",
        _example_invalid_request(),
    )


if __name__ == "__main__":
    asyncio.run(main())
