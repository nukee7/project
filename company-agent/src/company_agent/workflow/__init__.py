"""Research workflow engine — the sequential pipeline."""

from company_agent.workflow.pipeline import ResearchPipeline
from company_agent.workflow.steps import (
    PipelineStep,
    Step1IdentityResolution,
    Step1AMarketCapClassification,
    Step2ResearchPlan,
    Step3RetrieveEvidence,
    Step4ExtractEvidence,
    Step5SynthesizeResearch,
    Step6BuildWorkProduct,
)
from company_agent.workflow.context import WorkflowContext

__all__ = [
    "ResearchPipeline",
    "PipelineStep",
    "WorkflowContext",
    "Step1IdentityResolution",
    "Step1AMarketCapClassification",
    "Step2ResearchPlan",
    "Step3RetrieveEvidence",
    "Step4ExtractEvidence",
    "Step5SynthesizeResearch",
    "Step6BuildWorkProduct",
]
