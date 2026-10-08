"""Company Agent orchestrator.

This is the top-level entry point for running company research. It:
1. Validates the incoming request.
2. Creates a WorkflowContext with the request and tool registry.
3. Runs the research pipeline.
4. Returns the CompanyResearchResponse.

The agent itself is stateless — all state lives in the WorkflowContext
for the duration of a single request.
"""

from __future__ import annotations

import logging

from company_agent.contracts.request import CompanyResearchRequest
from company_agent.contracts.response import CompanyResearchResponse
from company_agent.domain.enums import WorkProductStatus
from company_agent.tools.registry import ToolRegistry
from company_agent.workflow.context import WorkflowContext
from company_agent.workflow.pipeline import ResearchPipeline

logger = logging.getLogger(__name__)


class CompanyAgent:
    """Evidence-based company and stock research specialist.

    Usage:
        from company_agent.tools.stubs import create_stub_registry

        agent = CompanyAgent(tools=create_stub_registry())
        response = await agent.research(request)
    """

    def __init__(
        self,
        tools: ToolRegistry,
        pipeline: ResearchPipeline | None = None,
    ) -> None:
        self._tools = tools
        self._pipeline = pipeline or ResearchPipeline()

    async def research(
        self, request: CompanyResearchRequest
    ) -> CompanyResearchResponse:
        """Execute a company research request end-to-end.

        Args:
            request: A typed, validated research request.

        Returns:
            A CompanyResearchResponse with status, claims, evidence,
            thesis, and limitations.
        """
        logger.info(
            "CompanyAgent.research called: request_id=%s, issuer=%s",
            request.request_id,
            request.issuer_candidate,
        )

        # --- Step 0: Validate the request ---
        errors = request.validate()
        if errors:
            logger.warning("Request validation failed: %s", errors)
            return CompanyResearchResponse(
                request_id=request.request_id,
                status=WorkProductStatus.BLOCKED,
                summary=f"Request validation failed: {'; '.join(errors)}",
                open_questions=errors,
            )

        # --- Build context and run pipeline ---
        ctx = WorkflowContext(request=request, tools=self._tools)

        response = await self._pipeline.run(ctx)

        logger.info(
            "CompanyAgent.research complete: request_id=%s, status=%s, claims=%d",
            response.request_id,
            response.status.value,
            len(response.claims),
        )

        return response
