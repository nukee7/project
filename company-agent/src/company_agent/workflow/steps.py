"""The pipeline steps for company research.

Pipeline structure (with LLM integration):
  Step 1:   Identity resolution          (tool)
  Step 1A:  Market cap classification    (tool)
  Step 2:   Research plan                (LLM call #1 — light model)
  Step 3:   Retrieve sources             (tool)
  Step 4:   Extract evidence             (tool)
  Step 5:   Synthesize claims + thesis   (LLM call #2 — heavy model, merged old Steps 5+6)
  Step 5a:  Add engine-backed claims     (deterministic)
  Step 5b:  Conflict detection           (tool)
  Step 5c:  Claim validation             (tool)
  Step 6:   Build work product           (assembly)

Two LLM calls total. Everything else is tools and assembly.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from company_agent.contracts.response import (
    CompanyOverviewSection,
    CompanyResearchResponse,
    EvidenceSummarySection,
    FinancialEvidenceSection,
    IdentitySection,
    LimitationsSection,
    MonitoringSection,
    ResearchScopeSection,
    ThesisSection,
    ValuationContextSection,
)
from company_agent.domain.claims import Claim
from company_agent.domain.enums import (
    ClaimStatus,
    ClaimType,
    MarketCapClassification,
    SourceTier,
    WorkProductStatus,
)
from company_agent.workflow.context import ResearchPlan, WorkflowContext


def _uid() -> str:
    return uuid.uuid4().hex[:12]


# --- Base class ---


class PipelineStep(ABC):
    """Base class for all pipeline steps."""

    name: str = "unnamed_step"

    @abstractmethod
    async def execute(self, ctx: WorkflowContext) -> None:
        """Run this step, reading from and writing to the context."""
        ...


# --- Helper to build identity info strings for LLM prompts ---


def _get_issuer_name(ctx: WorkflowContext) -> str:
    if ctx.identity and ctx.identity.resolved_issuer:
        return ctx.identity.resolved_issuer.name
    return ctx.request.issuer_candidate


def _get_security_info(ctx: WorkflowContext) -> str:
    if ctx.identity and ctx.identity.resolved_security:
        sec = ctx.identity.resolved_security
        if sec.listings:
            l = sec.listings[0]
            return f"{l.ticker} on {l.exchange} ({l.currency}), {sec.share_class or 'common'}"
    return ctx.request.security_candidate or "no specific security"


def _get_market_cap_info(ctx: WorkflowContext) -> str:
    if ctx.market_cap and ctx.market_cap.classification != MarketCapClassification.UNKNOWN:
        mc = ctx.market_cap
        return f"{mc.classification.value} ({mc.market_cap_value} {mc.currency})"
    return "unknown"


# ---------------------------------------------------------------------------
# Step 1: Confirm the company, stock, and time period
# ---------------------------------------------------------------------------


class Step1IdentityResolution(PipelineStep):
    """Confirm the company separately from the stock.

    Uses: resolve_issuer_security tool.
    No LLM — this is a database/API lookup.
    """

    name = "step_1_identity_resolution"

    async def execute(self, ctx: WorkflowContext) -> None:
        ctx.log(self.name, "Resolving issuer and security identity")

        req = ctx.request
        try:
            resolution = await ctx.tools.resolve_issuer_security.resolve(
                issuer_candidate=req.issuer_candidate,
                security_candidate=req.security_candidate,
                exchange_hint=req.exchange_hint,
                as_of_date=req.requested_as_of,
            )
        except Exception as e:
            ctx.block(f"Identity resolution tool failed: {e}")
            return

        ctx.identity = resolution

        if resolution.confidence == "unresolved":
            ctx.block(
                f"Cannot safely identify the company or stock. "
                f"Candidates considered: {resolution.candidates_considered}. "
                f"Ambiguity: {resolution.unresolved_ambiguity}"
            )
            return

        if resolution.confidence == "low":
            ctx.mark_needs_review(
                f"Low confidence identity resolution for '{req.issuer_candidate}'. "
                f"Ambiguity: {resolution.unresolved_ambiguity}"
            )
            return

        if resolution.resolved_issuer is None:
            ctx.block(f"No issuer resolved for '{req.issuer_candidate}'")
            return

        ctx.log(
            self.name,
            f"Resolved: issuer='{_get_issuer_name(ctx)}', "
            f"security={_get_security_info(ctx)}, "
            f"confidence={resolution.confidence}",
        )


# ---------------------------------------------------------------------------
# Step 1A: Classify company size by market capitalization
# ---------------------------------------------------------------------------


class Step1AMarketCapClassification(PipelineStep):
    """Ask a deterministic service for market-cap classification.

    Uses: get_market_cap_classification tool.
    No LLM — this is a deterministic engine call.
    Never blocks the pipeline.
    """

    name = "step_1a_market_cap"

    async def execute(self, ctx: WorkflowContext) -> None:
        ctx.log(self.name, "Requesting market-cap classification")

        if ctx.identity is None or ctx.identity.resolved_issuer is None:
            ctx.add_limitation("Market-cap classification skipped: no resolved issuer")
            return

        issuer_name = _get_issuer_name(ctx)
        security_id = None
        if ctx.identity.resolved_security and ctx.identity.resolved_security.listings:
            security_id = ctx.identity.resolved_security.listings[0].ticker

        try:
            result = await ctx.tools.get_market_cap_classification.classify(
                issuer_name=issuer_name,
                security_identifier=security_id,
                as_of_date=ctx.request.requested_as_of,
                policy_version=ctx.request.market_cap_policy_version,
            )
        except Exception as e:
            ctx.add_limitation(f"Market-cap classification unavailable: {e}")
            return

        ctx.market_cap = result

        if result.classification == MarketCapClassification.UNKNOWN:
            ctx.add_limitation(
                f"Market-cap classification is UNKNOWN: {result.unavailable_reason}"
            )
        else:
            ctx.log(
                self.name,
                f"Classification: {result.classification.value}, "
                f"value={result.market_cap_value} {result.currency}, "
                f"policy={result.policy_version}",
            )


# ---------------------------------------------------------------------------
# Step 2: Create a research plan — LLM call #1
# ---------------------------------------------------------------------------


class Step2ResearchPlan(PipelineStep):
    """Generate a targeted research plan using the LLM.

    Uses: LLM provider (light model).
    The LLM reads the question and decides what evidence to find.
    Falls back to a deterministic plan if the LLM fails.
    """

    name = "step_2_research_plan"

    async def execute(self, ctx: WorkflowContext) -> None:
        ctx.log(self.name, "Creating research plan via LLM")

        req = ctx.request
        issuer_name = _get_issuer_name(ctx)
        security_info = _get_security_info(ctx)
        market_cap_info = _get_market_cap_info(ctx)

        try:
            llm_plan = await ctx.tools.llm.generate_research_plan(
                research_question=req.research_question,
                issuer_name=issuer_name,
                security_info=security_info,
                market_cap_info=market_cap_info,
                period_scope=req.period_scope,
                research_depth=req.research_depth.value,
            )

            plan = ResearchPlan(
                evidence_needs=llm_plan.evidence_needs,
                source_categories=llm_plan.source_categories or [
                    "regulatory_filings", "earnings_releases", "earnings_transcripts",
                ],
                extraction_queries=llm_plan.extraction_queries,
                notes=llm_plan.notes,
            )
            ctx.research_plan = plan

            ctx.log(
                self.name,
                f"LLM plan created: {len(plan.evidence_needs)} evidence needs, "
                f"{len(plan.source_categories)} source categories",
            )

        except Exception as e:
            ctx.log(self.name, f"LLM planning failed ({e}), using deterministic fallback")
            ctx.research_plan = self._fallback_plan(req)
            ctx.add_limitation(f"LLM planning unavailable, used deterministic fallback: {e}")

    @staticmethod
    def _fallback_plan(req) -> ResearchPlan:
        """Deterministic fallback if LLM is unavailable."""
        depth = req.research_depth.value
        evidence_needs = [
            {"category": "financial_reporting", "reason": "Core financials", "unanswered_question": f"Key financials for {req.period_scope}?"},
            {"category": "business_and_revenue_drivers", "reason": "Revenue model", "unanswered_question": "What drives revenue?"},
            {"category": "management_strategy_and_risks", "reason": "Disclosed risks", "unanswered_question": "What risks exist?"},
            {"category": "competitive_context", "reason": "Market position", "unanswered_question": "Competitive landscape?"},
        ]
        if depth in ("standard", "deep"):
            evidence_needs.append({"category": "counterevidence", "reason": "Bear case", "unanswered_question": "What could go wrong?"})

        source_categories = ["regulatory_filings", "earnings_releases", "earnings_transcripts"]
        if depth in ("standard", "deep"):
            source_categories.append("secondary_reporting")

        return ResearchPlan(
            evidence_needs=evidence_needs,
            source_categories=source_categories,
            notes=f"[Fallback plan] Depth: {depth}. Question: {req.research_question}",
        )


# ---------------------------------------------------------------------------
# Step 3: Retrieve and rank evidence (unchanged — tool only)
# ---------------------------------------------------------------------------


class Step3RetrieveEvidence(PipelineStep):
    """Search for and retrieve primary/secondary sources.

    Uses: search_primary_sources + retrieve_source_record tools.
    No LLM — this is API/database work.
    """

    name = "step_3_retrieve_evidence"

    async def execute(self, ctx: WorkflowContext) -> None:
        ctx.log(self.name, "Searching for and retrieving sources")

        if ctx.identity is None or ctx.identity.resolved_issuer is None:
            ctx.add_limitation("Source retrieval skipped: no resolved issuer")
            return

        issuer = ctx.identity.resolved_issuer
        req = ctx.request

        try:
            search_result = await ctx.tools.search_primary_sources.search(
                issuer_name=issuer.name,
                issuer_identifiers=issuer.identifiers if issuer.identifiers else None,
                period_scope=req.period_scope,
                source_types=(
                    ctx.research_plan.source_categories
                    if ctx.research_plan
                    else None
                ),
            )
        except Exception as e:
            ctx.add_limitation(f"Primary source search failed: {e}")
            ctx.status = WorkProductStatus.PARTIAL
            return

        if not search_result.sources:
            ctx.add_limitation(
                f"No sources found for '{issuer.name}' in period '{req.period_scope}'"
            )
            ctx.status = WorkProductStatus.PARTIAL
            return

        ctx.log(
            self.name,
            f"Found {search_result.total_available} sources, "
            f"retrieved metadata for {len(search_result.sources)}",
        )

        for source_meta in search_result.sources:
            try:
                retrieved = await ctx.tools.retrieve_source_record.retrieve(
                    source_id=source_meta.source_id,
                    source_url=source_meta.source_url,
                )
                if retrieved:
                    ctx.sources.append(retrieved)
            except Exception as e:
                ctx.log(self.name, f"Failed to retrieve source {source_meta.source_id}: {e}")
                ctx.add_limitation(f"Source '{source_meta.title}' could not be retrieved: {e}")

        ctx.log(self.name, f"Successfully retrieved {len(ctx.sources)} source records")

        if not ctx.sources:
            ctx.add_limitation("All source retrieval attempts failed")
            ctx.status = WorkProductStatus.PARTIAL


# ---------------------------------------------------------------------------
# Step 4: Extract atomic evidence (unchanged — tool only)
# ---------------------------------------------------------------------------


class Step4ExtractEvidence(PipelineStep):
    """Extract bounded evidence records from each retrieved source.

    Uses: extract_evidence tool (which may internally use parsers or LLM).
    The pipeline step itself just calls the tool per source.
    """

    name = "step_4_extract_evidence"

    async def execute(self, ctx: WorkflowContext) -> None:
        ctx.log(self.name, "Extracting atomic evidence from sources")

        if not ctx.sources:
            ctx.add_limitation("Evidence extraction skipped: no sources available")
            return

        research_question = ctx.request.research_question
        issuer_scope = _get_issuer_name(ctx)

        for source in ctx.sources:
            try:
                records = await ctx.tools.extract_evidence.extract(
                    source=source,
                    extraction_query=research_question,
                    scope=issuer_scope,
                )
                ctx.evidence_records.extend(records)
            except Exception as e:
                ctx.log(self.name, f"Failed to extract from source {source.source_id}: {e}")
                ctx.add_limitation(f"Evidence extraction failed for '{source.title}': {e}")

        ctx.log(
            self.name,
            f"Extracted {len(ctx.evidence_records)} evidence records "
            f"from {len(ctx.sources)} sources",
        )

        if not ctx.evidence_records:
            ctx.add_limitation("No evidence records extracted from any source")
            ctx.status = WorkProductStatus.PARTIAL


# ---------------------------------------------------------------------------
# Step 5: Synthesize claims + thesis — LLM call #2 (merged old Steps 5+6)
# ---------------------------------------------------------------------------


class Step5SynthesizeResearch(PipelineStep):
    """Synthesize claims, thesis, and company overview from evidence.

    Uses: LLM provider (heavy model) for synthesis,
          then deterministic post-processing:
          - 5a: Add engine-backed claims (market cap)
          - 5b: Conflict detection (tool)
          - 5c: Claim validation (tool)

    This is the ONE call that does all the reasoning.
    """

    name = "step_5_synthesize"

    async def execute(self, ctx: WorkflowContext) -> None:
        ctx.log(self.name, "Synthesizing claims, thesis, and overview via LLM")

        issuer_name = _get_issuer_name(ctx)
        security_info = _get_security_info(ctx)
        market_cap_info = _get_market_cap_info(ctx)

        # --- LLM synthesis call ---
        if ctx.evidence_records:
            evidence_texts = [
                {
                    "evidence_id": ev.evidence_id,
                    "source_title": ev.source.title,
                    "excerpt": ev.excerpt,
                    "period": ev.applicable_period or "",
                    "source_tier": ev.source.source_tier.value,
                }
                for ev in ctx.evidence_records
            ]

            try:
                synthesis = await ctx.tools.llm.synthesize_research(
                    research_question=ctx.request.research_question,
                    issuer_name=issuer_name,
                    security_info=security_info,
                    market_cap_info=market_cap_info,
                    period_scope=ctx.request.period_scope,
                    evidence_texts=evidence_texts,
                )

                # Convert LLM claims to domain Claims
                for lc in synthesis.claims:
                    claim_type = ClaimType.SOURCED_FACT
                    if lc.claim_type == "inference":
                        claim_type = ClaimType.INFERENCE
                    elif lc.claim_type == "opinion":
                        claim_type = ClaimType.OPINION

                    ctx.claims.append(Claim(
                        claim_id=f"claim_{_uid()}",
                        claim_type=claim_type,
                        statement=lc.statement,
                        scope=issuer_name,
                        time_period=lc.time_period,
                        evidence_ids=lc.evidence_ids,
                        status=ClaimStatus.UNVERIFIED,
                    ))

                # Convert LLM thesis to domain ThesisSection
                t = synthesis.thesis
                ctx.thesis = ThesisSection(
                    hypothesis=t.hypothesis,
                    supporting_evidence=[c.claim_id for c in ctx.claims],
                    assumptions=t.assumptions,
                    bull_case=t.bull_case,
                    bear_case=t.bear_case,
                    catalysts=t.catalysts,
                    risks=t.risks,
                    validation_signals=t.validation_signals,
                    invalidation_conditions=t.invalidation_conditions,
                )

                # Convert LLM company overview
                o = synthesis.company_overview
                ctx.company_overview = CompanyOverviewSection(
                    business_description=o.business_description,
                    revenue_drivers=o.revenue_drivers,
                    competitive_position=o.competitive_position,
                    supporting_claims=[c.claim_id for c in ctx.claims[:5]],
                )

                # Add LLM-identified limitations
                for lim in synthesis.limitations:
                    ctx.add_limitation(lim)

                ctx.log(
                    self.name,
                    f"LLM synthesis complete: {len(ctx.claims)} claims, "
                    f"thesis hypothesis='{t.hypothesis[:80]}...'",
                )

            except Exception as e:
                ctx.log(self.name, f"LLM synthesis failed ({e}), using fallback")
                ctx.add_limitation(f"LLM synthesis unavailable: {e}")
                self._fallback_claims(ctx)
        else:
            ctx.add_limitation("Synthesis skipped: no evidence records")
            self._fallback_claims(ctx)

        # --- 5a: Add engine-backed claims (deterministic) ---
        if ctx.market_cap and ctx.market_cap.classification != MarketCapClassification.UNKNOWN:
            mc = ctx.market_cap
            ctx.claims.append(Claim(
                claim_id=f"claim_{_uid()}",
                claim_type=ClaimType.CALCULATED_RESULT,
                statement=(
                    f"Market capitalization classified as {mc.classification.value} "
                    f"({mc.market_cap_value} {mc.currency}) as of {mc.as_of_date}"
                ),
                scope=issuer_name,
                calculation_id=mc.calculation_id,
                status=ClaimStatus.SUPPORTED,
            ))

        # --- 5b: Conflict detection (tool) ---
        if ctx.evidence_records:
            try:
                conflict_result = await ctx.tools.find_source_conflicts.find_conflicts(
                    evidence_records=ctx.evidence_records,
                    scope=issuer_name,
                )
                if conflict_result.conflicts_found:
                    ctx.log(self.name, f"Found {len(conflict_result.conflicts)} source conflicts")
                    for conflict in conflict_result.conflicts:
                        ctx.add_limitation(
                            f"Source conflict: {conflict.get('description', 'Unknown')}"
                        )
                        conflict_scope = conflict.get("claim_scope", "")
                        for claim in ctx.claims:
                            if conflict_scope and conflict_scope in claim.scope:
                                claim.status = ClaimStatus.CONTESTED
                                claim.conflict_explanation = conflict.get("description")
            except Exception as e:
                ctx.log(self.name, f"Conflict detection failed: {e}")
                ctx.add_limitation(f"Source conflict detection unavailable: {e}")

        # --- 5c: Claim validation (tool) ---
        if ctx.claims:
            try:
                validation_result = await ctx.tools.validate_claims.validate(
                    claims=ctx.claims,
                    evidence_records=ctx.evidence_records,
                )
                for claim in ctx.claims:
                    if claim.claim_id in validation_result.valid_claims:
                        if claim.status == ClaimStatus.UNVERIFIED:
                            claim.status = ClaimStatus.SUPPORTED
                for issue in validation_result.issues:
                    ctx.log(
                        self.name,
                        f"Validation issue: {issue.get('claim_id')} — {issue.get('issue')}",
                    )
            except Exception as e:
                ctx.log(self.name, f"Claim validation failed: {e}")
                ctx.add_limitation(f"Claim validation unavailable: {e}")

        supported = sum(1 for c in ctx.claims if c.status == ClaimStatus.SUPPORTED)
        contested = sum(1 for c in ctx.claims if c.status == ClaimStatus.CONTESTED)
        ctx.log(
            self.name,
            f"Final: {len(ctx.claims)} claims, {supported} supported, {contested} contested",
        )

    @staticmethod
    def _fallback_claims(ctx: WorkflowContext) -> None:
        """Create basic claims from evidence when LLM is unavailable."""
        issuer_name = _get_issuer_name(ctx)
        for ev in ctx.evidence_records:
            ctx.claims.append(Claim(
                claim_id=f"claim_{_uid()}",
                claim_type=ClaimType.SOURCED_FACT,
                statement=ev.excerpt,
                scope=issuer_name,
                time_period=ev.applicable_period,
                evidence_ids=[ev.evidence_id],
                status=ClaimStatus.UNVERIFIED,
            ))


# ---------------------------------------------------------------------------
# Step 6: Build work product (was Step 7, renumbered)
# ---------------------------------------------------------------------------


class Step6BuildWorkProduct(PipelineStep):
    """Assemble the final CompanyResearchResponse from accumulated context.

    No LLM, no tool calls (except optional valuation context).
    This step always runs — even if the pipeline is blocked.
    """

    name = "step_6_build_work_product"

    async def execute(self, ctx: WorkflowContext) -> None:
        ctx.log(self.name, "Assembling final work product")

        # --- Identity section ---
        identity_section = None
        if ctx.identity:
            identity_section = IdentitySection(
                resolution=ctx.identity,
                notes=ctx.blocked_reason if ctx.is_blocked else None,
            )

        # --- Research scope section ---
        research_scope = ResearchScopeSection(
            research_question=ctx.request.research_question,
            requested_as_of=str(ctx.request.requested_as_of),
            period_scope=ctx.request.period_scope,
            research_depth=ctx.request.research_depth,
            invocation_context=ctx.request.invocation_context,
        )

        # --- Evidence summary section ---
        primary = [s for s in ctx.sources if s.source_tier in (
            SourceTier.PRIMARY_FILING, SourceTier.PRIMARY_ISSUER, SourceTier.OFFICIAL_NOTICE
        )]
        secondary = [s for s in ctx.sources if s.source_tier in (
            SourceTier.SECONDARY_LICENSED, SourceTier.OPINION
        )]
        periods = list({
            ev.applicable_period
            for ev in ctx.evidence_records
            if ev.applicable_period
        })

        evidence_summary = EvidenceSummarySection(
            primary_sources=primary,
            secondary_sources=secondary,
            source_count=len(ctx.sources),
            periods_covered=sorted(periods),
        )

        # --- Company overview section (from LLM or placeholder) ---
        issuer_name = _get_issuer_name(ctx)
        company_overview = ctx.company_overview or CompanyOverviewSection(
            business_description=f"Overview of {issuer_name} (awaiting synthesis).",
            supporting_claims=[c.claim_id for c in ctx.claims[:5]],
        )

        # --- Financial evidence section ---
        financial_claims = [
            c for c in ctx.claims if c.claim_type == ClaimType.SOURCED_FACT
        ]
        financial_periods = list({
            c.time_period for c in financial_claims if c.time_period
        })
        financial_evidence = FinancialEvidenceSection(
            claims=financial_claims,
            periods_covered=sorted(financial_periods),
        )

        # --- Valuation context section ---
        valuation_context = ValuationContextSection(available=False)
        try:
            val_result = await ctx.tools.get_valuation_context.get_valuation(
                issuer_name=issuer_name,
                as_of_date=ctx.request.requested_as_of,
            )
            if val_result.get("available"):
                valuation_context = ValuationContextSection(
                    available=True,
                    method=str(val_result.get("method", "")),
                    inputs_description=str(val_result.get("inputs", "")),
                    calculation_id=str(val_result.get("calculation_id", "")),
                    as_of_date=str(ctx.request.requested_as_of),
                    result_summary=str(val_result.get("summary", "")),
                )
        except Exception as e:
            ctx.log(self.name, f"Valuation context unavailable: {e}")

        # --- Monitoring section ---
        monitoring = MonitoringSection(
            monitoring_signals=(ctx.thesis.validation_signals if ctx.thesis else []),
            refresh_triggers=[
                "New quarterly/annual filing published",
                "Earnings release or guidance update",
                "Material corporate event",
            ],
            invalidation_conditions=(ctx.thesis.invalidation_conditions if ctx.thesis else []),
        )

        # --- Limitations section ---
        limitations_section = LimitationsSection(
            evidence_gaps=ctx.limitations,
            source_conflicts=[lim for lim in ctx.limitations if "conflict" in lim.lower()],
            stale_sources=[lim for lim in ctx.limitations if "stale" in lim.lower()],
            scope_exclusions=[],
        )

        # --- Summary ---
        status = ctx.status
        if status == WorkProductStatus.BLOCKED:
            summary = f"Research blocked: {ctx.blocked_reason}"
        elif status == WorkProductStatus.NEEDS_REVIEW:
            summary = f"Research needs review: {ctx.blocked_reason}"
        elif status == WorkProductStatus.PARTIAL:
            summary = (
                f"Partial research for {issuer_name}: "
                f"{len(ctx.claims)} claims from {len(ctx.sources)} sources. "
                f"Some evidence gaps remain."
            )
        else:
            summary = (
                f"Research complete for {issuer_name}: "
                f"{len(ctx.claims)} claims from {len(ctx.sources)} sources "
                f"covering {', '.join(periods) if periods else ctx.request.period_scope}."
            )

        # --- Assemble ---
        ctx._response = CompanyResearchResponse(  # type: ignore[attr-defined]
            request_id=ctx.request.request_id,
            status=status,
            summary=summary,
            identity=identity_section,
            research_scope=research_scope,
            evidence_summary=evidence_summary,
            company_overview=company_overview,
            financial_evidence=financial_evidence,
            market_cap_classification=ctx.market_cap,
            valuation_context=valuation_context,
            thesis=ctx.thesis,
            monitoring=monitoring,
            limitations=limitations_section,
            claims=ctx.claims,
            calculation_refs=[c.calculation_id for c in ctx.claims if c.calculation_id],
            evidence_refs=[ev.evidence_id for ev in ctx.evidence_records],
            open_questions=ctx.open_questions,
            trace_refs=ctx.trace_log,
            created_at=datetime.now(),
        )

        ctx.log(
            self.name,
            f"Work product assembled: status={status.value}, "
            f"claims={len(ctx.claims)}, sources={len(ctx.sources)}",
        )
