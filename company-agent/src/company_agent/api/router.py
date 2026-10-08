"""Route handlers for the Company Agent API.

Thin layer — translates HTTP to domain calls and back.
All intelligence lives in the agent and pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends

from company_agent.agent import CompanyAgent
from company_agent.api.dependencies import get_agent
from company_agent.api.schemas import ResearchRequestBody, ResearchResponseBody

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check — confirms the service is running."""
    return {
        "status": "ok",
        "service": "company-agent",
        "timestamp": datetime.now().isoformat(),
    }


@router.post(
    "/research",
    response_model=ResearchResponseBody,
    summary="Submit a company research request",
    description=(
        "Accepts a typed research request and returns a bounded work product "
        "with identity resolution, evidence, claims, thesis, and limitations. "
        "Even blocked or partial results return HTTP 200 — check the 'status' "
        "field in the response body for the research outcome."
    ),
    responses={
        200: {
            "description": (
                "Research work product. Check 'status' field: "
                "complete, partial, blocked, or needs_review."
            ),
        },
        422: {
            "description": (
                "Request validation failed — malformed JSON, wrong types, "
                "or missing required fields."
            ),
        },
    },
)
async def research(
    body: ResearchRequestBody,
    agent: CompanyAgent = Depends(get_agent),
) -> ResearchResponseBody:
    """Run company research and return the work product.

    Three lines of logic:
    1. Convert Pydantic model → domain dataclass
    2. Call the agent
    3. Convert domain response → Pydantic model
    """
    logger.info(
        "API /research called: request_id=%s, issuer=%s",
        body.request_id,
        body.issuer_candidate,
    )

    # Pydantic → domain
    domain_request = body.to_domain()

    # Run the agent (validation + pipeline)
    domain_response = await agent.research(domain_request)

    # Domain → Pydantic
    api_response = ResearchResponseBody.from_domain(domain_response)

    logger.info(
        "API /research complete: request_id=%s, status=%s",
        api_response.request_id,
        api_response.status.value,
    )

    return api_response
