"""Query route — ask questions about your portfolio.

This is the main research endpoint. Takes natural language,
runs the pipeline, returns structured answer.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from portfolio_agent.auth.dependencies import get_current_user
from portfolio_agent.api.state import app_state
from portfolio_agent.workflow.pipeline import run_portfolio_query

router = APIRouter()


class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        description="Natural language question about your portfolio",
        examples=["What are my top holdings?", "Tell me about Reliance Industries"],
    )


class QueryResponse(BaseModel):
    question: str
    intent: str
    answer: str
    key_findings: list[str] = []
    risks_and_limitations: list[str] = []
    follow_up_questions: list[str] = []
    portfolio_snapshot: dict = {}
    calculations: dict = {}
    research: list[dict] = []
    trace: list[str] = []
    processing_time_seconds: float = 0.0
    timestamp: str = ""


@router.post("/query", response_model=QueryResponse, summary="Ask a question about your portfolio")
async def query(
    body: QueryRequest,
    user: dict = Depends(get_current_user),
) -> QueryResponse:
    """Ask a natural language question about your portfolio.

    The Portfolio Agent will:
    1. Understand your question
    2. Look at your portfolio holdings
    3. Run calculations (allocation, exposure, concentration)
    4. Delegate to the Company Agent for stock research if needed
    5. Synthesize a clear answer with evidence
    """
    portfolio = app_state.portfolio_store.get_portfolio(user["user_id"])
    if not portfolio or not portfolio.positions:
        raise HTTPException(
            status_code=400,
            detail="No portfolio found. Add positions first via POST /portfolio/positions",
        )

    result = await run_portfolio_query(
        question=body.question,
        portfolio=portfolio,
        llm=app_state.llm,
        delegator=app_state.delegator,
    )

    return QueryResponse(
        question=result["question"],
        intent=result.get("intent", "unknown"),
        answer=result["answer"],
        key_findings=result.get("key_findings", []),
        risks_and_limitations=result.get("risks_and_limitations", []),
        follow_up_questions=result.get("follow_up_questions", []),
        portfolio_snapshot=result.get("portfolio_snapshot", {}),
        calculations=result.get("calculations", {}),
        research=result.get("research", []),
        trace=result.get("trace", []),
        processing_time_seconds=result.get("processing_time_seconds", 0.0),
        timestamp=datetime.now().isoformat(),
    )


@router.get("/health", summary="Health check")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "portfolio-agent",
        "timestamp": datetime.now().isoformat(),
        "llm_available": app_state.llm.is_available if app_state.llm else False,
    }
