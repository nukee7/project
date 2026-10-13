"""Pipeline runner — executes the research workflow in sequence.

The runner checks ctx.is_blocked between steps. If blocked,
remaining steps are skipped EXCEPT the final build step,
which always runs to produce a structured partial response.
"""

from __future__ import annotations

import logging
import time

from company_agent.contracts.response import CompanyResearchResponse
from shared.domain.enums import WorkProductStatus
from company_agent.workflow.context import WorkflowContext
from company_agent.workflow.steps import (
    PipelineStep,
    Step1IdentityResolution,
    Step1AMarketCapClassification,
    Step2ResearchPlan,
    Step3RetrieveEvidence,
    Step3ASecondaryReporting,
    Step4ExtractEvidence,
    Step5SynthesizeResearch,
    Step6BuildWorkProduct,
)

logger = logging.getLogger(__name__)


class ResearchPipeline:
    """Runs the Company Agent's research pipeline.

    Steps execute in order. If a step blocks the context, all subsequent
    steps are skipped except the final assembly step.

    Pipeline:
      Step 1:   Identity resolution          (tool)
      Step 1A:  Market cap classification    (tool)
      Step 2:   Research plan                (LLM #1)
      Step 3:   Retrieve sources             (tool)
      Step 4:   Extract evidence             (tool)
      Step 5:   Synthesize claims + thesis   (LLM #2 + tools)
      Step 6:   Build work product           (assembly, always runs)
    """

    def __init__(self, steps: list[PipelineStep] | None = None) -> None:
        if steps is not None:
            self._steps = steps
        else:
            self._steps = self._default_steps()
        self._final_step = Step6BuildWorkProduct()

    @staticmethod
    def _default_steps() -> list[PipelineStep]:
        """The standard pipeline (minus the final assembly step)."""
        return [
            Step1IdentityResolution(),
            Step1AMarketCapClassification(),
            Step2ResearchPlan(),
            Step3RetrieveEvidence(),
            Step3ASecondaryReporting(),
            Step4ExtractEvidence(),
            Step5SynthesizeResearch(),
        ]

    async def run(self, ctx: WorkflowContext) -> CompanyResearchResponse:
        """Execute the pipeline and return the assembled work product."""
        start_time = time.time()
        ctx.log("pipeline", "Starting research pipeline")

        for step in self._steps:
            if ctx.is_blocked:
                ctx.log("pipeline", f"Skipping {step.name}: pipeline is {ctx.status.value}")
                continue

            ctx.log("pipeline", f"Executing {step.name}")
            try:
                await step.execute(ctx)
            except Exception as e:
                ctx.log("pipeline", f"Unhandled error in {step.name}: {e}")
                ctx.add_limitation(f"Step {step.name} failed with error: {e}")
                if not ctx.is_blocked:
                    ctx.status = WorkProductStatus.PARTIAL

        # Final step always runs
        ctx.log("pipeline", f"Executing {self._final_step.name} (always runs)")
        try:
            await self._final_step.execute(ctx)
        except Exception as e:
            ctx.log("pipeline", f"Fatal: work product assembly failed: {e}")
            return CompanyResearchResponse(
                request_id=ctx.request.request_id,
                status=WorkProductStatus.BLOCKED,
                summary=f"Work product assembly failed: {e}",
                trace_refs=ctx.trace_log,
            )

        elapsed = time.time() - start_time
        ctx.log("pipeline", f"Pipeline complete in {elapsed:.2f}s")

        response: CompanyResearchResponse = ctx._response  # type: ignore[attr-defined]
        response.processing_time_seconds = elapsed

        return response
