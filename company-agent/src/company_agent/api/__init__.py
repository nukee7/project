"""API layer for the Company Agent.

Translates between HTTP/JSON and the domain layer.
The domain, contracts, tools, and workflow are untouched.
"""

from company_agent.api.app import create_app

__all__ = ["create_app"]
