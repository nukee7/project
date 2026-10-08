"""FastAPI application factory.

Creates the app with lifespan management, CORS middleware,
and the research router.

Run with:
    uvicorn company_agent.api.app:create_app --factory --reload

Or:
    python -m company_agent.api.app
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from company_agent.api.dependencies import init_agent, shutdown_agent
from company_agent.api.router import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """App startup and shutdown lifecycle.

    Startup:  creates the CompanyAgent with the configured tools.
    Shutdown: cleans up agent resources.
    """
    logger.info("Starting Company Agent API")
    init_agent()  # Uses stub tools by default; pass real registry for production
    logger.info("CompanyAgent initialized with tool registry")
    yield
    shutdown_agent()
    logger.info("Company Agent API shut down")


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title="Company Agent API",
        description=(
            "Evidence-based company and stock research specialist. "
            "Accepts typed research requests and returns bounded work products "
            "with identity resolution, sourced evidence, claims, thesis, and limitations."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — allow all origins in development, restrict in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount the router
    app.include_router(router)

    return app


# Allow running directly: python -m company_agent.api.app
if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "company_agent.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=True,
    )
