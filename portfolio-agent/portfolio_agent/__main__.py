"""Entry point: python -m portfolio_agent"""

from portfolio_agent.api.app import create_app
import uvicorn
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

host = os.getenv("HOST", "127.0.0.1")
port = int(os.getenv("PORT", "8001"))

uvicorn.run(
    "portfolio_agent.api.app:create_app",
    factory=True,
    host=host,
    port=port,
    log_level="info",
)
