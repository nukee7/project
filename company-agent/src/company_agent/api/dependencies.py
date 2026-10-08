"""Dependency injection for the API layer.

The CompanyAgent and ToolRegistry are created once at app startup
and injected into route handlers via FastAPI's Depends() system.

LLM configuration:
- If OPENAI_API_KEY is set → uses OpenAI provider (GPT-3.5-turbo by default)
- If not set → uses stub LLM provider (no API calls, template responses)

Override models via environment variables:
    LLM_MODEL_LIGHT=gpt-4o-mini   (for Step 2: planning)
    LLM_MODEL_HEAVY=gpt-4o        (for Step 5: synthesis)
"""

from __future__ import annotations

import logging
import os

from company_agent.agent import CompanyAgent
from company_agent.tools.registry import ToolRegistry
from company_agent.testing.stubs import create_stub_registry
from company_agent.testing.stub_llm import StubLLMProvider

logger = logging.getLogger(__name__)

# Module-level state — set during app lifespan
_agent: CompanyAgent | None = None
_tools: ToolRegistry | None = None


def _create_default_registry() -> ToolRegistry:
    """Create a ToolRegistry, auto-detecting LLM provider from environment.

    If OPENAI_API_KEY is set, uses OpenAI. Otherwise uses stubs.
    All non-LLM tools use stubs regardless (swap for real tools later).
    """
    registry = create_stub_registry()

    # Try to upgrade to real OpenAI LLM if API key is available
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        try:
            from company_agent.tools.llm.openai_provider import OpenAILLMProvider
            registry.llm = OpenAILLMProvider(api_key=api_key)
            logger.info(
                "Using OpenAI LLM provider (light=%s, heavy=%s)",
                os.getenv("LLM_MODEL_LIGHT", "gpt-3.5-turbo"),
                os.getenv("LLM_MODEL_HEAVY", "gpt-3.5-turbo"),
            )
        except Exception as e:
            logger.warning("Failed to initialize OpenAI provider, using stubs: %s", e)
    else:
        logger.info("No OPENAI_API_KEY set — using stub LLM provider")

    return registry


def init_agent(tools: ToolRegistry | None = None) -> CompanyAgent:
    """Create and store the CompanyAgent singleton.

    Called once during app startup (lifespan). Pass a custom ToolRegistry
    for production; defaults to auto-detected configuration.
    """
    global _agent, _tools
    _tools = tools or _create_default_registry()
    _agent = CompanyAgent(tools=_tools)
    return _agent


def shutdown_agent() -> None:
    """Clean up agent resources on shutdown."""
    global _agent, _tools
    _agent = None
    _tools = None


def get_agent() -> CompanyAgent:
    """FastAPI dependency — returns the CompanyAgent instance.

    Usage in a route handler:
        @router.post("/research")
        async def research(agent: CompanyAgent = Depends(get_agent)):
            ...
    """
    if _agent is None:
        raise RuntimeError(
            "CompanyAgent not initialized. "
            "Call init_agent() during app startup."
        )
    return _agent
