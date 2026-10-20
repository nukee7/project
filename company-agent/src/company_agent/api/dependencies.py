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
from test.company_agent.stubs import create_stub_registry
from test.company_agent.stub_llm import StubLLMProvider

logger = logging.getLogger(__name__)

# Module-level state — set during app lifespan
_agent: CompanyAgent | None = None
_tools: ToolRegistry | None = None


def _create_default_registry() -> ToolRegistry:
    """Create a ToolRegistry, auto-detecting available providers.

    Real BSE India primary tools are always used (free, no key needed).
    OpenAI LLM is used if OPENAI_API_KEY is set, otherwise stub LLM.
    Remaining tools (identity, market_cap, claims, conflicts) use stubs.
    """
    registry = create_stub_registry()

    # Upgrade shared tools to real implementations (free, no API key)
    try:
        from shared.tools.implementations.bse_identity import BseIdentityResolver
        registry.resolve_issuer_security = BseIdentityResolver()
        logger.info("Using real BSE identity resolver")
    except Exception as e:
        logger.warning("Failed to init identity resolver: %s", e)

    try:
        from shared.tools.implementations.yahoo_market_cap import YahooMarketCapClassifier
        registry.get_market_cap_classification = YahooMarketCapClassifier()
        logger.info("Using real Yahoo Finance market cap classifier")
    except Exception as e:
        logger.warning("Failed to init market cap classifier: %s", e)

    try:
        from shared.tools.implementations.conflict_detector import RealConflictDetector
        registry.find_source_conflicts = RealConflictDetector()
        logger.info("Using real conflict detector")
    except Exception as e:
        logger.warning("Failed to init conflict detector: %s", e)

    try:
        from shared.tools.implementations.claim_validator import RealClaimValidator
        registry.validate_claims = RealClaimValidator()
        logger.info("Using real claim validator")
    except Exception as e:
        logger.warning("Failed to init claim validator: %s", e)

    # Upgrade to real primary tools — BSE India (free, no API key)
    try:
        from company_agent.tools.primary.text_store import FilingTextStore
        from company_agent.tools.primary.search import PrimarySearchSources
        from company_agent.tools.primary.retrieve import PrimaryRetrieveSource
        from company_agent.tools.primary.extract import PrimaryExtractEvidence

        text_store = FilingTextStore()
        registry.search_primary_sources = PrimarySearchSources()
        registry.retrieve_source_record = PrimaryRetrieveSource(text_store=text_store)
        registry.extract_evidence = PrimaryExtractEvidence(text_store=text_store)
        logger.info("Using real BSE India primary tools for search, retrieval, and extraction")
    except Exception as e:
        logger.warning("Failed to initialize primary tools, using stubs: %s", e)

    # Upgrade to real secondary reporting + valuation tool (free, no API key)
    # SecondarySourceAggregator implements BOTH search() and get_valuation()
    try:
        from company_agent.tools.secondary.aggregator import SecondarySourceAggregator
        registry.search_secondary_sources = SecondarySourceAggregator()
        logger.info("Using real secondary tool (Google News India + Yahoo Finance for news, stats, and valuation)")
    except Exception as e:
        logger.warning("Failed to initialize secondary reporting tool, using stubs: %s", e)

    # Upgrade to real OpenAI LLM if API key is available
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
