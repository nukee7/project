"""FastAPI application for the Portfolio Agent.

Run with:
    uvicorn portfolio_agent.api.app:create_app --factory --reload --port 8001
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from portfolio_agent.api.routes_auth import router as auth_router
from portfolio_agent.api.routes_portfolio import router as portfolio_router
from portfolio_agent.api.routes_query import router as query_router
from portfolio_agent.api.state import app_state

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting Portfolio Agent API")
    app_state.initialize()
    logger.info("Portfolio Agent initialized")
    yield
    logger.info("Portfolio Agent shut down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Portfolio Agent API",
        description=(
            "Portfolio-centric investment research system. "
            "Manage your portfolio, ask questions, get evidence-based research."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
    app.include_router(portfolio_router, prefix="/portfolio", tags=["Portfolio"])
    app.include_router(query_router, tags=["Research"])

    return app


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("portfolio_agent.api.app:create_app", factory=True, host=host, port=port, reload=True)
