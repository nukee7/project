"""Production entry point for the Company Agent.

Starts the FastAPI server with real tool configuration.
Requires OPENAI_API_KEY environment variable for LLM features.

Run with:
    python -m company_agent
    python -m company_agent.main

Environment variables:
    OPENAI_API_KEY       — Required. Your OpenAI API key.
    LLM_MODEL_LIGHT      — Optional. Model for planning (default: gpt-3.5-turbo)
    LLM_MODEL_HEAVY      — Optional. Model for synthesis (default: gpt-3.5-turbo)
    HOST                 — Optional. Server host (default: 127.0.0.1)
    PORT                 — Optional. Server port (default: 8000)
    CORS_ORIGINS         — Optional. Comma-separated allowed origins (default: *)
    LOG_LEVEL            — Optional. Logging level (default: INFO)
"""

from __future__ import annotations

import logging
import os
import sys


def main() -> None:
    """Start the Company Agent API server."""
    import uvicorn

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    logger = logging.getLogger(__name__)

    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning(
            "OPENAI_API_KEY is not set. The agent will use stub LLM responses. "
            "Set the environment variable for real research analysis."
        )
    else:
        logger.info("OPENAI_API_KEY detected — using OpenAI LLM provider")

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))

    logger.info("Starting Company Agent API on %s:%d", host, port)
    logger.info(
        "LLM config: light=%s, heavy=%s",
        os.getenv("LLM_MODEL_LIGHT", "gpt-3.5-turbo"),
        os.getenv("LLM_MODEL_HEAVY", "gpt-3.5-turbo"),
    )
    logger.info("API docs at http://%s:%d/docs", host, port)

    uvicorn.run(
        "company_agent.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        log_level=log_level.lower(),
    )


if __name__ == "__main__":
    main()
