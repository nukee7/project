"""Shared application state — stores, LLM, delegator, pricing.

Initialized once at app startup. Accessed by route handlers.
"""

from __future__ import annotations

import logging
import os

from portfolio_agent.store.user_store import UserStore
from portfolio_agent.store.portfolio_store import PortfolioStore
from portfolio_agent.orchestration.llm import PortfolioLLM
from portfolio_agent.orchestration.delegator import AgentDelegator

logger = logging.getLogger(__name__)


class AppState:
    """Singleton holding all shared state for the application."""

    def __init__(self) -> None:
        self.user_store: UserStore | None = None
        self.portfolio_store: PortfolioStore | None = None
        self.llm: PortfolioLLM | None = None
        self.delegator: AgentDelegator | None = None
        self.price_fetcher = None  # GetCurrentPrice implementation

    def initialize(self) -> None:
        self.user_store = UserStore()
        self.portfolio_store = PortfolioStore()
        self.llm = PortfolioLLM(api_key=os.getenv("OPENAI_API_KEY"))
        self.delegator = AgentDelegator()

        # Initialize price fetcher
        try:
            from shared.tools.implementations.yahoo_pricing import YahooPriceFetcher
            self.price_fetcher = YahooPriceFetcher()
            logger.info("Using Yahoo Finance price fetcher")
        except Exception as e:
            logger.warning("Price fetcher unavailable: %s", e)


app_state = AppState()
