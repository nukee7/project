"""Testing and development utilities for the Company Agent.

This package contains stub implementations and example runners
for running the pipeline without real external services.

NOT for production use.
"""

from company_agent.testing.stubs import create_stub_registry
from company_agent.testing.stub_llm import StubLLMProvider

__all__ = ["create_stub_registry", "StubLLMProvider"]
