"""Portfolio Agent pipeline.

Steps:
  1. Load portfolio context
  2. Understand + Plan (LLM call #1)
  3. Run calculations (deterministic)
  4. Delegate to specialists (Company Agent)
  5. Synthesize answer (LLM call #2)
  6. Build response

2 LLM calls total. Calculations and delegation are tool/engine work.
"""

from __future__ import annotations

import json
import logging
import time

from portfolio_agent.models.portfolio import Portfolio
from portfolio_agent.orchestration.llm import PortfolioLLM
from portfolio_agent.orchestration.calculations import calculate_allocation, calculate_concentration
from portfolio_agent.orchestration.delegator import AgentDelegator

logger = logging.getLogger(__name__)


def _portfolio_summary(portfolio: Portfolio) -> str:
    """Build a text summary of the portfolio for LLM prompts."""
    if not portfolio.positions:
        return "No positions in portfolio."

    lines: list[str] = []
    for p in portfolio.positions:
        value = p.current_value or p.invested_value
        lines.append(
            f"  {p.ticker} ({p.name}) — {p.position_type.value}, "
            f"qty: {p.quantity}, invested: ₹{p.invested_value:,.0f}, "
            f"sector: {p.sector or 'Unknown'}"
        )
    return "\n".join(lines)


async def run_portfolio_query(
    question: str,
    portfolio: Portfolio,
    llm: PortfolioLLM,
    delegator: AgentDelegator,
) -> dict:
    """Execute the full portfolio query pipeline.

    Returns a dict with: answer, key_findings, calculations, research,
    limitations, trace, processing_time.
    """
    start = time.time()
    trace: list[str] = []

    def log(step: str, msg: str):
        entry = f"[{step}] {msg}"
        trace.append(entry)
        logger.info(entry)

    # --- Step 1: Load portfolio context ---
    log("step_1", f"Portfolio loaded: {portfolio.position_count} positions, ₹{portfolio.total_invested:,.0f} invested")

    summary_text = _portfolio_summary(portfolio)

    # --- Step 2: Understand + Plan (LLM #1) ---
    log("step_2", "Understanding query and planning execution")

    plan = await llm.understand_and_plan(
        question=question,
        portfolio_summary=summary_text,
        position_count=portfolio.position_count,
        total_invested=portfolio.total_invested,
    )

    intent = plan.get("intent", "general_question")
    log("step_2", f"Intent: {intent}. Summary: {plan.get('summary', question)}")

    needs_calc = plan.get("needs_calculation", False)
    needs_research = plan.get("needs_company_research", False)
    research_targets = plan.get("company_research_targets", [])

    log("step_2", f"Plan: calc={needs_calc}, research={needs_research}, targets={len(research_targets)}")

    # --- Step 3: Run calculations (deterministic) ---
    calc_results: dict = {}

    if needs_calc:
        log("step_3", "Running portfolio calculations")

        calc_types = plan.get("calculation_types", ["allocation"])

        if "allocation" in calc_types or "exposure" in calc_types:
            calc_results["allocation"] = calculate_allocation(portfolio)
            log("step_3", f"Allocation calculated: {calc_results['allocation']['position_count']} positions")

        if "concentration" in calc_types:
            calc_results["concentration"] = calculate_concentration(portfolio)
            log("step_3", f"Concentration: {calc_results['concentration']['concentration_level']}")

        # Default: always calculate allocation if any calculation requested
        if not calc_results:
            calc_results["allocation"] = calculate_allocation(portfolio)
    else:
        log("step_3", "No calculations needed")

    # --- Step 4: Delegate to specialists ---
    research_results: list[dict] = []

    if needs_research and research_targets:
        log("step_4", f"Delegating research for {len(research_targets)} companies")

        for target in research_targets:
            ticker = target.get("ticker", "")
            name = target.get("name", ticker)
            rq = target.get("question", question)

            log("step_4", f"Researching {ticker} ({name})")
            result = await delegator.research_company(
                ticker=ticker,
                name=name,
                question=rq,
            )
            research_results.append(result)
            log("step_4", f"Research for {ticker}: {result.get('status', 'unknown')}")
    else:
        log("step_4", "No delegation needed")

    # --- Step 5: Synthesize answer (LLM #2) ---
    log("step_5", "Synthesizing answer")

    calc_text = json.dumps(calc_results, indent=2, default=str) if calc_results else ""
    research_text = json.dumps(research_results, indent=2, default=str) if research_results else ""

    synthesis = await llm.synthesize_answer(
        question=question,
        portfolio_summary=summary_text,
        calculation_results=calc_text,
        research_results=research_text,
    )

    log("step_5", "Synthesis complete")

    # --- Step 6: Build response ---
    elapsed = time.time() - start
    log("step_6", f"Pipeline complete in {elapsed:.2f}s")

    return {
        "question": question,
        "intent": intent,
        "plan_summary": plan.get("summary", question),
        "answer": synthesis.get("answer", "Unable to generate answer."),
        "key_findings": synthesis.get("key_findings", []),
        "risks_and_limitations": synthesis.get("risks_and_limitations", []),
        "follow_up_questions": synthesis.get("follow_up_questions", []),
        "calculations": calc_results,
        "research": research_results,
        "portfolio_snapshot": {
            "position_count": portfolio.position_count,
            "total_invested": portfolio.total_invested,
            "total_current_value": portfolio.total_current_value,
            "as_of": str(portfolio.as_of),
        },
        "trace": trace,
        "processing_time_seconds": round(elapsed, 3),
    }
