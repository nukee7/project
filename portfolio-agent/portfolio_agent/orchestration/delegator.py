"""Delegation to specialist agents.

Calls the Company Agent directly (same process import) for company research.
Mutual Fund Agent delegation is stubbed — returns "not yet available".
"""

from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)


class AgentDelegator:
    """Delegates research to Company Agent (and later Mutual Fund Agent)."""

    def __init__(self) -> None:
        self._company_agent = None
        self._company_tools = None

    async def _get_company_agent(self):
        """Lazy-load the Company Agent to avoid circular imports."""
        if self._company_agent is None:
            from company_agent.agent import CompanyAgent
            from company_agent.api.dependencies import _create_default_registry
            self._company_tools = _create_default_registry()
            self._company_agent = CompanyAgent(tools=self._company_tools)
        return self._company_agent

    async def research_company(
        self,
        ticker: str,
        name: str,
        question: str,
        period_scope: str = "FY2023-FY2024",
        as_of_date: date | None = None,
        invocation_context: str = "direct_position",
    ) -> dict:
        """Delegate company research to the Company Agent.

        Returns a simplified dict with key findings, not the full work product.
        """
        logger.info("Delegating company research: %s (%s)", name, ticker)

        try:
            from company_agent.contracts.request import (
                AuthorizedSources,
                CompanyResearchRequest,
            )
            from shared.domain.enums import InvocationContext, ResearchDepth

            agent = await self._get_company_agent()

            request = CompanyResearchRequest(
                request_id=f"portfolio-delegate-{ticker}",
                invocation_context=InvocationContext(invocation_context),
                research_question=question,
                issuer_candidate=name,
                security_candidate=ticker,
                exchange_hint="BSE",
                requested_as_of=as_of_date or date.today(),
                period_scope=period_scope,
                authorized_sources=AuthorizedSources(),
                caller_context=f"Portfolio Agent delegation for direct holding: {ticker}",
                research_depth=ResearchDepth.STANDARD,
                market_cap_policy_version="v1.0",
            )

            response = await agent.research(request)

            # Extract key info for the Portfolio Agent
            result = {
                "ticker": ticker,
                "name": name,
                "status": response.status.value,
                "summary": response.summary,
                "claims_count": len(response.claims),
            }

            if response.company_overview:
                result["business_description"] = response.company_overview.business_description
                result["revenue_drivers"] = response.company_overview.revenue_drivers
                result["competitive_position"] = response.company_overview.competitive_position

            if response.thesis:
                result["hypothesis"] = response.thesis.hypothesis
                result["bull_case"] = response.thesis.bull_case
                result["bear_case"] = response.thesis.bear_case
                result["risks"] = response.thesis.risks
                result["catalysts"] = response.thesis.catalysts

            if response.market_cap_classification:
                mc = response.market_cap_classification
                result["market_cap"] = mc.classification.value
                result["market_cap_value"] = mc.market_cap_value

            if response.limitations:
                result["limitations"] = response.limitations.evidence_gaps

            # Key claims as text
            result["key_claims"] = [
                f"({c.claim_type.value}) {c.statement}"
                for c in response.claims[:5]
            ]

            logger.info(
                "Company research complete: %s → %s, %d claims",
                ticker, response.status.value, len(response.claims),
            )

            return result

        except Exception as e:
            logger.error("Company research delegation failed for %s: %s", ticker, e)
            return {
                "ticker": ticker,
                "name": name,
                "status": "error",
                "summary": f"Research delegation failed: {e}",
            }

    async def analyze_fund(self, fund_id: str, fund_name: str, question: str) -> dict:
        """Delegate fund analysis to the Mutual Fund Agent.

        NOT YET IMPLEMENTED — returns a placeholder.
        """
        logger.info("Fund analysis requested for %s — not yet available", fund_name)
        return {
            "fund_id": fund_id,
            "fund_name": fund_name,
            "status": "unavailable",
            "summary": "Mutual Fund Agent is not yet implemented. Fund-level analysis will be available in a future release.",
        }
