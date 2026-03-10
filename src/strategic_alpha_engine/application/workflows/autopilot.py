from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pydantic import Field

from strategic_alpha_engine.application.contracts import (
    AutopilotIterationRecord,
    AutopilotManifest,
    CandidateArtifactRecord,
    CandidateStageRecord,
    EvaluationArtifactRecord,
    HumanReviewArtifactRecord,
    HumanReviewQueueRecord,
    PromotionArtifactRecord,
    SimulationArtifactRecord,
    SubmissionPacketArtifactRecord,
    SubmissionPacketIndexRecord,
    SubmissionReadyArtifactRecord,
    SubmissionReadyCandidateRecord,
    ValidationBacklogEntry,
    ValidationPromotionArtifactRecord,
    RunStateRecord,
)
from strategic_alpha_engine.application.services import (
    AgendaGenerator,
    ArtifactLedger,
    BrainSimulationClient,
    FamilyAnalyticsBuilder,
    ResearchAgendaManager,
    StateLedger,
    candidate_signature,
)
from strategic_alpha_engine.application.workflows.evaluate_stage_a import StageAEvaluationWorkflow
from strategic_alpha_engine.application.workflows.generate_submission_packet import (
    SubmissionPacketBundle,
    SubmissionPacketResult,
    SubmissionPacketWorkflow,
)
from strategic_alpha_engine.application.workflows.plan import PlanWorkflow
from strategic_alpha_engine.application.workflows.promote_robust_candidates import (
    RobustPromotionOutcome,
    RobustPromotionWorkflow,
)
from strategic_alpha_engine.application.workflows.review_submission_ready import HumanReviewWorkflow
from strategic_alpha_engine.application.workflows.simulate import (
    SimulationExecutionPolicy,
    SimulationOrchestratorWorkflow,
)
from strategic_alpha_engine.application.workflows.synthesize import (
    CandidateEvaluation,
    SynthesizeResult,
    SynthesizeWorkflow,
)
from strategic_alpha_engine.application.workflows.validate import (
    MultiPeriodValidateWorkflow,
)
from strategic_alpha_engine.config import RuntimeSettings
from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.enums import (
    AutopilotStopReason,
    CandidateLifecycleStage,
    HumanReviewDecisionKind,
    HumanReviewQueueStatus,
    PromotionDecisionKind,
    RunKind,
    RunLifecycleStatus,
    ValidationBacklogStatus,
    ValidationStage,
)
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.promotion import PromotionDecision
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.review import HumanReviewDecision
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _build_run_id(prefix: str, family: str) -> str:
    timestamp = _utc_now().strftime("%Y%m%dT%H%M%S%fZ")
    return f"{prefix}.{family}.{timestamp}"


def _build_agenda_queue_records(
    *,
    run_id: str,
    iteration_index: int,
    agendas: list[ResearchAgenda],
    agenda_recommendations,
    selected_agenda_id: str | None,
    recorded_at: datetime,
):
    records: list = []
    agendas_by_id = {agenda.agenda_id: agenda for agenda in agendas}
    from strategic_alpha_engine.application.contracts.state import AgendaQueueRecord

    for rank, recommendation in enumerate(agenda_recommendations, start=1):
        agenda = agendas_by_id[recommendation.agenda_id]
        records.append(
            AgendaQueueRecord(
                queue_record_id=f"queue.{run_id}.{iteration_index:03d}.{rank:03d}",
                source_run_id=run_id,
                iteration_index=iteration_index,
                rank=rank,
                agenda_id=agenda.agenda_id,
                family=agenda.family,
                agenda_name=agenda.name,
                agenda_status=agenda.status,
                base_priority=recommendation.base_priority,
                family_score=recommendation.family_score,
                adjusted_priority=recommendation.adjusted_priority,
                selected_for_execution=agenda.agenda_id == selected_agenda_id,
                reasons=recommendation.reasons,
                recorded_at=recorded_at,
            )
        )
    return records


def _build_candidate_stage_records(
    *,
    run_id: str,
    hypothesis,
    synthesize_result: SynthesizeResult,
    stage_a_result,
    default_recorded_at: datetime,
) -> list[CandidateStageRecord]:
    stage_records: list[CandidateStageRecord] = []
    outcome_by_candidate_id = {
        outcome.candidate.candidate_id: outcome
        for outcome in stage_a_result.outcomes
    }

    for evaluation in synthesize_result.evaluations:
        candidate_id = evaluation.candidate.candidate_id
        if evaluation.critique is None or not evaluation.critique.passes:
            stage_records.append(
                CandidateStageRecord(
                    stage_record_id=f"stage.{run_id}.{candidate_id}.rejected",
                    candidate_id=candidate_id,
                    hypothesis_id=hypothesis.hypothesis_id,
                    blueprint_id=synthesize_result.blueprint.blueprint_id,
                    family=hypothesis.family,
                    stage=CandidateLifecycleStage.REJECTED,
                    source_run_id=run_id,
                    recorded_at=default_recorded_at,
                    notes="rejected before simulation",
                )
            )
            continue

        stage_records.append(
            CandidateStageRecord(
                stage_record_id=f"stage.{run_id}.{candidate_id}.critique_passed",
                candidate_id=candidate_id,
                hypothesis_id=hypothesis.hypothesis_id,
                blueprint_id=synthesize_result.blueprint.blueprint_id,
                family=hypothesis.family,
                stage=CandidateLifecycleStage.CRITIQUE_PASSED,
                source_run_id=run_id,
                recorded_at=default_recorded_at,
                notes="passed critique and advanced to simulation",
            )
        )

        outcome = outcome_by_candidate_id.get(candidate_id)
        if outcome is None:
            continue

        stage_records.append(
            CandidateStageRecord(
                stage_record_id=f"stage.{run_id}.{candidate_id}.{outcome.promotion.to_stage}",
                candidate_id=candidate_id,
                hypothesis_id=hypothesis.hypothesis_id,
                blueprint_id=synthesize_result.blueprint.blueprint_id,
                family=hypothesis.family,
                stage=outcome.promotion.to_stage,
                source_run_id=run_id,
                recorded_at=outcome.promotion.decided_at,
                notes=f"promotion decision: {outcome.promotion.decision}"[:240],
            )
        )

    return stage_records


def _build_robust_candidate_stage_records(
    *,
    run_id: str,
    hypothesis,
    blueprint,
    promotion_result,
) -> list[CandidateStageRecord]:
    records: list[CandidateStageRecord] = []
    for outcome in promotion_result.outcomes:
        records.append(
            CandidateStageRecord(
                stage_record_id=f"stage.{run_id}.{outcome.candidate.candidate_id}.{outcome.promotion.to_stage}",
                candidate_id=outcome.candidate.candidate_id,
                hypothesis_id=hypothesis.hypothesis_id,
                blueprint_id=blueprint.blueprint_id,
                family=hypothesis.family,
                stage=outcome.promotion.to_stage,
                source_run_id=run_id,
                recorded_at=outcome.promotion.decided_at,
                notes=f"robust promotion decision: {outcome.promotion.decision}"[:240],
            )
        )
    return records


def _build_submission_ready_stage_records(
    *,
    run_id: str,
    hypothesis,
    blueprint,
    records: list[SubmissionReadyArtifactRecord],
) -> list[CandidateStageRecord]:
    stage_records: list[CandidateStageRecord] = []
    for record in records:
        stage_records.append(
            CandidateStageRecord(
                stage_record_id=f"stage.{run_id}.{record.candidate.candidate_id}.submission_ready",
                candidate_id=record.candidate.candidate_id,
                hypothesis_id=hypothesis.hypothesis_id,
                blueprint_id=blueprint.blueprint_id,
                family=hypothesis.family,
                stage=CandidateLifecycleStage.SUBMISSION_READY,
                source_run_id=run_id,
                recorded_at=record.submission_promotion.decided_at,
                notes="autopilot selected candidate for packet generation",
            )
        )
    return stage_records


def _build_human_review_stage_records(
    *,
    run_id: str,
    hypothesis,
    blueprint,
    review_result,
) -> list[CandidateStageRecord]:
    records: list[CandidateStageRecord] = []
    for outcome in review_result.outcomes:
        records.append(
            CandidateStageRecord(
                stage_record_id=(
                    f"stage.{run_id}.{outcome.submission_ready.candidate.candidate_id}."
                    f"{outcome.review_decision.to_stage}"
                ),
                candidate_id=outcome.submission_ready.candidate.candidate_id,
                hypothesis_id=hypothesis.hypothesis_id,
                blueprint_id=blueprint.blueprint_id,
                family=hypothesis.family,
                stage=outcome.review_decision.to_stage,
                source_run_id=run_id,
                recorded_at=outcome.review_decision.reviewed_at,
                notes="autopilot synthetic approve review",
            )
        )
    return records


def _latest_candidate_stage_records(
    records: list[CandidateStageRecord],
) -> dict[str, CandidateStageRecord]:
    latest: dict[str, CandidateStageRecord] = {}
    for record in records:
        latest[record.candidate_id] = record
    return latest


def _build_validation_backlog_entries(
    *,
    run_id: str,
    candidates: list[ExpressionCandidate],
    family,
    validation_stage: ValidationStage,
    periods: list[str],
    created_at: datetime,
) -> list[ValidationBacklogEntry]:
    entries: list[ValidationBacklogEntry] = []
    priority = 0.85 if validation_stage == ValidationStage.STAGE_B else 0.7
    for period in periods:
        for candidate in candidates:
            entries.append(
                ValidationBacklogEntry(
                    backlog_entry_id=f"backlog.{run_id}.{candidate.candidate_id}.{period}.completed",
                    candidate_id=candidate.candidate_id,
                    family=family,
                    requested_period=period,
                    validation_stage=validation_stage.value,
                    priority=priority,
                    status=ValidationBacklogStatus.COMPLETED,
                    source_run_id=run_id,
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
    return entries


def _candidate_stage_rank(stage: CandidateLifecycleStage) -> int:
    order = [
        CandidateLifecycleStage.DRAFT,
        CandidateLifecycleStage.CRITIQUE_PASSED,
        CandidateLifecycleStage.SIM_PASSED,
        CandidateLifecycleStage.ROBUST_CANDIDATE,
        CandidateLifecycleStage.SUBMISSION_READY,
        CandidateLifecycleStage.REJECTED,
    ]
    return order.index(stage)


class AutopilotCandidateBundle(EngineModel):
    agenda: ResearchAgenda
    hypothesis: HypothesisSpec
    blueprint: SignalBlueprint
    candidate_artifact: CandidateArtifactRecord
    simulation_artifact: SimulationArtifactRecord
    evaluation_artifact: EvaluationArtifactRecord
    stage_a_promotion: PromotionArtifactRecord
    robust_promotion: ValidationPromotionArtifactRecord
    validation_records: list = Field(default_factory=list)


class AutopilotWorkflowResult(EngineModel):
    autopilot_run_id: str
    stopped_reason: AutopilotStopReason
    manifest: AutopilotManifest
    iteration_records: list[AutopilotIterationRecord] = Field(default_factory=list)
    agenda_catalog_count: int = 0
    selected_candidate_ids: list[str] = Field(default_factory=list)
    packet_ids: list[str] = Field(default_factory=list)
    packet_paths: list[str] = Field(default_factory=list)
    packet_index_added_count: int = 0


class AutopilotWorkflow:
    def __init__(
        self,
        *,
        settings: RuntimeSettings,
        agenda_generator: AgendaGenerator,
        agenda_manager: ResearchAgendaManager,
        plan_workflow: PlanWorkflow,
        synthesize_workflow: SynthesizeWorkflow,
        brain_client: BrainSimulationClient,
        stage_a_workflow: StageAEvaluationWorkflow,
        validate_workflow: MultiPeriodValidateWorkflow,
        robust_promotion_workflow: RobustPromotionWorkflow,
        human_review_workflow: HumanReviewWorkflow,
        submission_packet_workflow: SubmissionPacketWorkflow,
        artifact_ledger: ArtifactLedger,
        state_ledger: StateLedger,
        family_analytics_builder: FamilyAnalyticsBuilder,
        max_polls: int,
    ):
        self.settings = settings
        self.agenda_generator = agenda_generator
        self.agenda_manager = agenda_manager
        self.plan_workflow = plan_workflow
        self.synthesize_workflow = synthesize_workflow
        self.brain_client = brain_client
        self.stage_a_workflow = stage_a_workflow
        self.validate_workflow = validate_workflow
        self.robust_promotion_workflow = robust_promotion_workflow
        self.human_review_workflow = human_review_workflow
        self.submission_packet_workflow = submission_packet_workflow
        self.artifact_ledger = artifact_ledger
        self.state_ledger = state_ledger
        self.family_analytics_builder = family_analytics_builder
        self.max_polls = max_polls

    def run(
        self,
        *,
        autopilot_run_id: str,
        artifacts_dir: str | Path,
        seed_agendas: list[ResearchAgenda] | None = None,
    ) -> AutopilotWorkflowResult:
        started_at = _utc_now()
        self.state_ledger.append_run_state_records(
            [
                self._build_started_run_state(
                    run_id=autopilot_run_id,
                    run_kind=RunKind.AUTOPILOT,
                    started_at=started_at,
                    parent_run_id=None,
                )
            ]
        )

        agenda_catalog = list(seed_agendas or [])
        recent_failed_families: list = []
        candidate_pool: dict[str, AutopilotCandidateBundle] = {}
        used_agenda_ids: set[str] = set()
        iteration_records: list[AutopilotIterationRecord] = []
        idle_rounds = 0
        stop_reason = AutopilotStopReason.AGENDA_GENERATION_EXHAUSTED
        total_simulations = 0

        try:
            learner_summaries = self._refresh_family_analytics(artifacts_dir)
            generated = self.agenda_generator.generate(
                existing_agendas=agenda_catalog,
                queue_depth=len(self._available_agendas(agenda_catalog, used_agenda_ids)),
                learner_summaries=learner_summaries,
                recent_failed_families=recent_failed_families,
            )
            agenda_catalog.extend(generated)
            agenda_catalog = self._dedupe_agendas(agenda_catalog)
            self.artifact_ledger.write_agenda_catalog_records(autopilot_run_id, agenda_catalog)
            self.artifact_ledger.write_agenda_generation_summary(
                autopilot_run_id,
                self._build_agenda_generation_summary(agenda_catalog, generated),
            )

            while True:
                selected_candidate_ids = self._select_candidate_ids_for_manifest(candidate_pool)
                if len(selected_candidate_ids) >= self.settings.autopilot.target_packet_count:
                    stop_reason = AutopilotStopReason.TARGET_PACKET_COUNT_REACHED
                    break
                if idle_rounds >= self.settings.autopilot.idle_rounds:
                    stop_reason = AutopilotStopReason.IDLE_ROUND_LIMIT_REACHED
                    break
                if len(used_agenda_ids) >= self.settings.autopilot.max_agendas:
                    stop_reason = AutopilotStopReason.MAX_AGENDAS_REACHED
                    break
                if total_simulations >= self.settings.autopilot.max_simulations:
                    stop_reason = AutopilotStopReason.MAX_SIMULATIONS_REACHED
                    break

                learner_summaries = self._refresh_family_analytics(artifacts_dir)
                available_agendas = self._available_agendas(agenda_catalog, used_agenda_ids)
                if len(available_agendas) <= self.settings.autopilot.min_queue_depth:
                    generated = self.agenda_generator.generate(
                        existing_agendas=agenda_catalog,
                        queue_depth=len(available_agendas),
                        learner_summaries=learner_summaries,
                        recent_failed_families=recent_failed_families,
                    )
                    if generated:
                        agenda_catalog.extend(generated)
                        agenda_catalog = self._dedupe_agendas(agenda_catalog)
                        available_agendas = self._available_agendas(agenda_catalog, used_agenda_ids)
                        self.artifact_ledger.write_agenda_catalog_records(autopilot_run_id, agenda_catalog)
                        self.artifact_ledger.write_agenda_generation_summary(
                            autopilot_run_id,
                            self._build_agenda_generation_summary(agenda_catalog, generated),
                        )

                family_recommendations = self._build_family_recommendations(learner_summaries)
                selection = self.agenda_manager.select_next(
                    available_agendas,
                    family_recommendations,
                    excluded_agenda_ids=used_agenda_ids,
                )
                selected_agenda = selection.selected_agenda
                if selected_agenda is None:
                    stop_reason = AutopilotStopReason.AGENDA_GENERATION_EXHAUSTED
                    break

                iteration_index = len(iteration_records) + 1
                queue_records = _build_agenda_queue_records(
                    run_id=autopilot_run_id,
                    iteration_index=iteration_index,
                    agendas=available_agendas,
                    agenda_recommendations=selection.agenda_recommendations,
                    selected_agenda_id=selected_agenda.agenda_id,
                    recorded_at=_utc_now(),
                )
                self.state_ledger.append_agenda_queue_records(queue_records)
                used_agenda_ids.add(selected_agenda.agenda_id)

                iteration_bundle_map, simulate_run_id, validate_run_id, simulated_candidate_count = self._run_iteration(
                    autopilot_run_id=autopilot_run_id,
                    agenda=selected_agenda,
                    artifacts_dir=artifacts_dir,
                )
                total_simulations += simulated_candidate_count
                if not iteration_bundle_map:
                    recent_failed_families.append(selected_agenda.family)
                else:
                    for candidate_id, bundle in iteration_bundle_map.items():
                        candidate_pool[candidate_id] = bundle

                current_selected_ids = self._select_candidate_ids_for_manifest(candidate_pool)
                if set(current_selected_ids) == set(selected_candidate_ids):
                    idle_rounds += 1
                else:
                    idle_rounds = 0

                if not iteration_bundle_map:
                    recent_failed_families = recent_failed_families[-16:]

                iteration_records.append(
                    AutopilotIterationRecord(
                        iteration_record_id=f"autopilot_iteration.{autopilot_run_id}.{iteration_index:03d}",
                        autopilot_run_id=autopilot_run_id,
                        iteration_index=iteration_index,
                        agenda_id=selected_agenda.agenda_id,
                        agenda_name=selected_agenda.name,
                        family=selected_agenda.family,
                        simulate_run_id=simulate_run_id,
                        validate_run_id=validate_run_id,
                        promoted_candidate_ids=sorted(
                            candidate_id
                            for candidate_id, bundle in iteration_bundle_map.items()
                            if bundle.robust_promotion.promotion.to_stage == CandidateLifecycleStage.ROBUST_CANDIDATE
                        ),
                        held_candidate_ids=sorted(
                            candidate_id
                            for candidate_id, bundle in iteration_bundle_map.items()
                            if bundle.robust_promotion.promotion.to_stage == CandidateLifecycleStage.SIM_PASSED
                        ),
                        rejected_candidate_ids=sorted(
                            candidate_id
                            for candidate_id, bundle in iteration_bundle_map.items()
                            if bundle.robust_promotion.promotion.to_stage == CandidateLifecycleStage.REJECTED
                        ),
                        manifest_candidate_ids=current_selected_ids,
                        queue_depth_after_iteration=len(self._available_agendas(agenda_catalog, used_agenda_ids)),
                        recorded_at=_utc_now(),
                    )
                )

            self.artifact_ledger.write_autopilot_iterations(autopilot_run_id, iteration_records)
            packet_result, packet_index_records, manifest = self._finalize_packet_flow(
                autopilot_run_id=autopilot_run_id,
                artifacts_dir=artifacts_dir,
                candidate_pool=candidate_pool,
                stopped_reason=stop_reason,
            )
            self.artifact_ledger.write_autopilot_manifest(autopilot_run_id, manifest)
            self.state_ledger.write_latest_submission_manifest(manifest)
            if packet_index_records:
                self.state_ledger.append_submission_packet_index_records(packet_index_records)

            completed_at = _utc_now()
            self.state_ledger.append_run_state_records(
                [
                    RunStateRecord(
                        run_id=autopilot_run_id,
                        run_kind=RunKind.AUTOPILOT,
                        status=RunLifecycleStatus.COMPLETED,
                        started_at=started_at,
                        completed_at=completed_at,
                        candidate_count=len(candidate_pool),
                    )
                ]
            )
            packet_paths = [
                str(Path(artifacts_dir).expanduser().resolve() / "runs" / packet_result.source_run_id / "packets" / f"{packet.candidate_artifact.candidate.candidate_id}.json")
                for packet in packet_result.packets
            ] if packet_result is not None else []
            return AutopilotWorkflowResult(
                autopilot_run_id=autopilot_run_id,
                stopped_reason=stop_reason,
                manifest=manifest,
                iteration_records=iteration_records,
                agenda_catalog_count=len(agenda_catalog),
                selected_candidate_ids=manifest.candidate_ids,
                packet_ids=manifest.packet_ids,
                packet_paths=packet_paths,
                packet_index_added_count=len(packet_index_records),
            )
        except Exception as exc:
            self.state_ledger.append_run_state_records(
                [
                    RunStateRecord(
                        run_id=autopilot_run_id,
                        run_kind=RunKind.AUTOPILOT,
                        status=RunLifecycleStatus.FAILED,
                        started_at=started_at,
                        completed_at=_utc_now(),
                        error_message=str(exc)[:300],
                    )
                ]
            )
            raise

    def _run_iteration(
        self,
        *,
        autopilot_run_id: str,
        agenda: ResearchAgenda,
        artifacts_dir: str | Path,
    ) -> tuple[dict[str, AutopilotCandidateBundle], str, str | None, int]:
        plan_result = self.plan_workflow.run(agenda)
        simulate_run_id = _build_run_id("simulate", agenda.family)
        simulate_started_at = _utc_now()
        self.state_ledger.append_run_state_records(
            [
                self._build_started_run_state(
                    run_id=simulate_run_id,
                    run_kind=RunKind.SIMULATE,
                    started_at=simulate_started_at,
                    parent_run_id=autopilot_run_id,
                )
            ]
        )

        try:
            synthesize_result = self.synthesize_workflow.run(
                hypothesis=plan_result.hypothesis,
                blueprint=plan_result.blueprint,
            )
            simulation_result = SimulationOrchestratorWorkflow(
                brain_client=self.brain_client,
                max_polls=self.max_polls,
            ).run(
                synthesize_result=synthesize_result,
                policy=self._build_simulation_policy(plan_result.hypothesis),
            )
            stage_a_result = self.stage_a_workflow.run(
                simulation_result,
                source_run_id=simulate_run_id,
            )
            self.artifact_ledger.write_synthesize_result(
                simulate_run_id,
                synthesize_result,
                agenda=agenda,
            )
            self.artifact_ledger.write_simulation_result(simulate_run_id, simulation_result)
            self.artifact_ledger.write_stage_a_result(simulate_run_id, stage_a_result)
            self.state_ledger.append_candidate_stage_records(
                _build_candidate_stage_records(
                    run_id=simulate_run_id,
                    hypothesis=plan_result.hypothesis,
                    synthesize_result=synthesize_result,
                    stage_a_result=stage_a_result,
                    default_recorded_at=simulate_started_at,
                )
            )
            self.state_ledger.append_run_state_records(
                [
                    RunStateRecord(
                        run_id=simulate_run_id,
                        run_kind=RunKind.SIMULATE,
                        status=RunLifecycleStatus.COMPLETED,
                        started_at=simulate_started_at,
                        parent_run_id=autopilot_run_id,
                        completed_at=_utc_now(),
                        candidate_count=len(synthesize_result.evaluations),
                        accepted_candidate_count=len(synthesize_result.accepted_candidate_ids),
                        simulated_candidate_count=len(simulation_result.simulated_candidate_ids),
                    )
                ]
            )
            self._refresh_family_analytics(artifacts_dir)
        except Exception as exc:
            self.state_ledger.append_run_state_records(
                [
                    RunStateRecord(
                        run_id=simulate_run_id,
                        run_kind=RunKind.SIMULATE,
                        status=RunLifecycleStatus.FAILED,
                        started_at=simulate_started_at,
                        parent_run_id=autopilot_run_id,
                        completed_at=_utc_now(),
                        error_message=str(exc)[:300],
                    )
                ]
            )
            raise

        stage_a_passed_ids = set(stage_a_result.promoted_candidate_ids)
        if not stage_a_passed_ids:
            return {}, simulate_run_id, None, len(simulation_result.simulated_candidate_ids)

        candidate_map = {
            evaluation.candidate.candidate_id: evaluation
            for evaluation in synthesize_result.evaluations
        }
        selected_candidates = [
            candidate_map[candidate_id].candidate
            for candidate_id in sorted(stage_a_passed_ids)
        ]
        validate_run_id = _build_run_id("validate", agenda.family)
        validate_started_at = _utc_now()
        self.state_ledger.append_run_state_records(
            [
                self._build_started_run_state(
                    run_id=validate_run_id,
                    run_kind=RunKind.VALIDATE,
                    started_at=validate_started_at,
                    parent_run_id=autopilot_run_id,
                )
            ]
        )
        try:
            validation_result = self.validate_workflow.run(
                source_run_id=validate_run_id,
                candidate_source_run_id=simulate_run_id,
                hypothesis=plan_result.hypothesis,
                blueprint=plan_result.blueprint,
                candidates=selected_candidates,
                validation_stage=ValidationStage.STAGE_B,
                periods=["P1Y0M0D", "P3Y0M0D", "P5Y0M0D"],
            )
            robust_promotion_result = self.robust_promotion_workflow.run(
                validation_result,
                candidates=selected_candidates,
                existing_robust_signature_counts=self._existing_robust_signature_counts(
                    self.state_ledger.load_candidate_stage_records(),
                    artifacts_dir,
                ),
            )
            self.artifact_ledger.write_validation_result(
                validate_run_id,
                validation_result,
                agenda=agenda,
            )
            self.artifact_ledger.write_robust_promotion_result(
                validate_run_id,
                robust_promotion_result,
            )
            self.state_ledger.append_candidate_stage_records(
                _build_robust_candidate_stage_records(
                    run_id=validate_run_id,
                    hypothesis=plan_result.hypothesis,
                    blueprint=plan_result.blueprint,
                    promotion_result=robust_promotion_result,
                )
            )
            self.state_ledger.append_validation_backlog_entries(
                _build_validation_backlog_entries(
                    run_id=validate_run_id,
                    candidates=selected_candidates,
                    family=plan_result.hypothesis.family,
                    validation_stage=ValidationStage.STAGE_B,
                    periods=["P1Y0M0D", "P3Y0M0D", "P5Y0M0D"],
                    created_at=validate_started_at,
                )
            )
            self.state_ledger.append_run_state_records(
                [
                    RunStateRecord(
                        run_id=validate_run_id,
                        run_kind=RunKind.VALIDATE,
                        status=RunLifecycleStatus.COMPLETED,
                        started_at=validate_started_at,
                        parent_run_id=autopilot_run_id,
                        completed_at=_utc_now(),
                        candidate_count=len(selected_candidates),
                    )
                ]
            )
            self._refresh_family_analytics(artifacts_dir)
        except Exception as exc:
            self.state_ledger.append_run_state_records(
                [
                    RunStateRecord(
                        run_id=validate_run_id,
                        run_kind=RunKind.VALIDATE,
                        status=RunLifecycleStatus.FAILED,
                        started_at=validate_started_at,
                        parent_run_id=autopilot_run_id,
                        completed_at=_utc_now(),
                        error_message=str(exc)[:300],
                    )
                ]
            )
            raise

        bundle_map = self._build_iteration_bundles(
            agenda=agenda,
            synthesize_result=synthesize_result,
            stage_a_result=stage_a_result,
            validation_result=validation_result,
            robust_promotion_result=robust_promotion_result,
        )
        return bundle_map, simulate_run_id, validate_run_id, len(simulation_result.simulated_candidate_ids)

    def _build_iteration_bundles(
        self,
        *,
        agenda: ResearchAgenda,
        synthesize_result: SynthesizeResult,
        stage_a_result,
        validation_result,
        robust_promotion_result,
    ) -> dict[str, AutopilotCandidateBundle]:
        candidate_artifacts = {
            evaluation.candidate.candidate_id: CandidateArtifactRecord(
                candidate=evaluation.candidate,
                validation=evaluation.validation,
                critique=evaluation.critique,
            )
            for evaluation in synthesize_result.evaluations
        }
        simulation_artifacts = {
            execution.candidate.candidate_id: SimulationArtifactRecord(
                simulation_request=execution.execution.simulation_request,
                simulation_run=execution.execution.simulation_run,
                submission=execution.execution.submission,
                poll_history=execution.execution.poll_history,
                result=execution.execution.result,
            )
            for execution in stage_a_result.outcomes
        }
        evaluation_artifacts = {
            outcome.candidate.candidate_id: EvaluationArtifactRecord(
                evaluation=outcome.evaluation,
                simulation_run=outcome.execution.simulation_run,
                result=outcome.execution.result,
            )
            for outcome in stage_a_result.outcomes
        }
        stage_a_promotions = {
            outcome.candidate.candidate_id: PromotionArtifactRecord(
                evaluation=outcome.evaluation,
                promotion=outcome.promotion,
            )
            for outcome in stage_a_result.outcomes
        }
        validation_records_by_candidate: dict[str, list] = defaultdict(list)
        for period_result in validation_result.period_results:
            for outcome in period_result.outcomes:
                validation_records_by_candidate[outcome.candidate.candidate_id].append(outcome.validation)

        bundles: dict[str, AutopilotCandidateBundle] = {}
        for outcome in robust_promotion_result.outcomes:
            candidate_id = outcome.candidate.candidate_id
            if outcome.promotion.to_stage != CandidateLifecycleStage.ROBUST_CANDIDATE:
                continue
            bundles[candidate_id] = AutopilotCandidateBundle(
                agenda=agenda,
                hypothesis=synthesize_result.hypothesis,
                blueprint=synthesize_result.blueprint,
                candidate_artifact=candidate_artifacts[candidate_id],
                simulation_artifact=simulation_artifacts[candidate_id],
                evaluation_artifact=evaluation_artifacts[candidate_id],
                stage_a_promotion=stage_a_promotions[candidate_id],
                robust_promotion=ValidationPromotionArtifactRecord(
                    candidate=outcome.candidate,
                    validation_stage=robust_promotion_result.validation_stage,
                    requested_periods=outcome.requested_periods,
                    validation_ids=[record.validation_id for record in outcome.validation_records],
                    passing_periods=outcome.passing_periods,
                    failing_periods=outcome.failing_periods,
                    aggregate_pass_decision=outcome.aggregate_pass_decision,
                    promotion=outcome.promotion,
                ),
                validation_records=sorted(
                    validation_records_by_candidate[candidate_id],
                    key=lambda record: record.period,
                ),
            )
        return bundles

    def _build_simulation_policy(self, hypothesis) -> SimulationExecutionPolicy:
        return SimulationExecutionPolicy(
            region=hypothesis.target_region or self.settings.region,
            universe=hypothesis.target_universe or self.settings.universe,
            delay=self.settings.simulation_delay,
            neutralization=self.settings.simulation_neutralization,
            test_period=self.settings.default_test_period,
        )

    def _refresh_family_analytics(self, artifacts_dir: str | Path):
        bundle = self.family_analytics_builder.build(
            artifacts_dir,
            candidate_stage_records=self.state_ledger.load_candidate_stage_records(),
        )
        self.state_ledger.write_family_stats(bundle.family_stats)
        self.state_ledger.write_family_learner_summaries(bundle.learner_summaries)
        return bundle.learner_summaries

    def _build_family_recommendations(self, learner_summaries):
        from strategic_alpha_engine.application.services.search_policy import HeuristicSearchPolicyLearner

        return HeuristicSearchPolicyLearner().recommend(learner_summaries)

    def _available_agendas(
        self,
        agenda_catalog: list[ResearchAgenda],
        used_agenda_ids: set[str],
    ) -> list[ResearchAgenda]:
        return [
            agenda
            for agenda in agenda_catalog
            if agenda.status in {"active", "backlog"} and agenda.agenda_id not in used_agenda_ids
        ]

    def _dedupe_agendas(self, agendas: list[ResearchAgenda]) -> list[ResearchAgenda]:
        from strategic_alpha_engine.application.services.agenda_generation import dedupe_agendas

        return dedupe_agendas(agendas)

    def _build_agenda_generation_summary(
        self,
        agenda_catalog: list[ResearchAgenda],
        generated_agendas: list[ResearchAgenda],
    ) -> dict:
        summary = getattr(self.agenda_generator, "last_summary", {})
        return {
            "generated_at": _utc_now().isoformat(),
            "agenda_catalog_count": len(agenda_catalog),
            "new_agenda_count": len(generated_agendas),
            **summary,
        }

    def _existing_robust_signature_counts(
        self,
        stage_records: list[CandidateStageRecord],
        artifacts_dir: str | Path,
    ) -> dict[str, int]:
        latest_stage_records = _latest_candidate_stage_records(stage_records)
        robust_candidate_ids = {
            candidate_id
            for candidate_id, record in latest_stage_records.items()
            if record.stage in {
                CandidateLifecycleStage.ROBUST_CANDIDATE,
                CandidateLifecycleStage.SUBMISSION_READY,
            }
        }
        if not robust_candidate_ids:
            return {}
        candidate_catalog: dict[str, ExpressionCandidate] = {}
        root = Path(artifacts_dir).expanduser().resolve()
        candidate_fields = set(ExpressionCandidate.model_fields)
        for path in sorted((root / "runs").glob("*/candidates.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                import json

                payload = json.loads(line)
                candidate = ExpressionCandidate(
                    **{
                        key: value
                        for key, value in payload.items()
                        if key in candidate_fields
                    }
                )
                candidate_catalog[candidate.candidate_id] = candidate

        counts: Counter[str] = Counter()
        for candidate_id in robust_candidate_ids:
            candidate = candidate_catalog.get(candidate_id)
            if candidate is None:
                continue
            counts[candidate_signature(candidate)] += 1
        return dict(counts)

    def _bundle_rank_key(self, bundle: AutopilotCandidateBundle) -> tuple:
        evaluation = bundle.evaluation_artifact.evaluation
        passing_period_count = len(bundle.robust_promotion.passing_periods)
        stage_a_sharpe = evaluation.sharpe if evaluation.sharpe is not None else float("-inf")
        fitness = evaluation.fitness if evaluation.fitness is not None else float("-inf")
        turnover_gap = (
            abs((evaluation.turnover or 0.25) - 0.25)
            if evaluation.turnover is not None
            else float("inf")
        )
        return (
            -passing_period_count,
            -stage_a_sharpe,
            -fitness,
            turnover_gap,
            bundle.candidate_artifact.candidate.candidate_id,
        )

    def _index_rank_key(self, record: SubmissionPacketIndexRecord) -> tuple:
        return (
            -record.passing_period_count,
            -(record.stage_a_sharpe if record.stage_a_sharpe is not None else float("-inf")),
            -(record.fitness if record.fitness is not None else float("-inf")),
            abs((record.turnover if record.turnover is not None else 0.25) - 0.25)
            if record.turnover is not None
            else float("inf"),
            record.candidate_id,
        )

    def _select_bundles_for_manifest(
        self,
        candidate_pool: dict[str, AutopilotCandidateBundle],
    ) -> list[AutopilotCandidateBundle]:
        min_stage = self.settings.autopilot.packet_min_stage
        deduped: dict[str, AutopilotCandidateBundle] = {}
        for bundle in candidate_pool.values():
            stage = bundle.robust_promotion.promotion.to_stage
            if _candidate_stage_rank(stage) < _candidate_stage_rank(min_stage):
                continue
            signature = candidate_signature(bundle.candidate_artifact.candidate)
            current = deduped.get(signature)
            if current is None or self._bundle_rank_key(bundle) < self._bundle_rank_key(current):
                deduped[signature] = bundle
        selected = sorted(deduped.values(), key=self._bundle_rank_key)
        return selected[: self.settings.autopilot.packet_top_k]

    def _select_candidate_ids_for_manifest(
        self,
        candidate_pool: dict[str, AutopilotCandidateBundle],
    ) -> list[str]:
        return [
            bundle.candidate_artifact.candidate.candidate_id
            for bundle in self._select_bundles_for_manifest(candidate_pool)
        ]

    def _group_bundles_by_context(
        self,
        bundles: list[AutopilotCandidateBundle],
    ) -> dict[tuple[str, str, str], list[AutopilotCandidateBundle]]:
        grouped: dict[tuple[str, str, str], list[AutopilotCandidateBundle]] = defaultdict(list)
        for bundle in bundles:
            grouped[
                (
                    bundle.agenda.agenda_id,
                    bundle.hypothesis.hypothesis_id,
                    bundle.blueprint.blueprint_id,
                )
            ].append(bundle)
        return grouped

    def _build_submission_ready_artifacts(
        self,
        *,
        run_id: str,
        bundles: list[AutopilotCandidateBundle],
        promoted_at: datetime,
    ) -> tuple[list[SubmissionReadyArtifactRecord], list[SubmissionReadyCandidateRecord]]:
        artifact_records: list[SubmissionReadyArtifactRecord] = []
        inventory_records: list[SubmissionReadyCandidateRecord] = []
        for bundle in bundles:
            candidate = bundle.candidate_artifact.candidate
            promotion = PromotionDecision(
                promotion_id=f"promotion.{run_id}.{candidate.candidate_id}.submission_ready",
                candidate_id=candidate.candidate_id,
                hypothesis_id=candidate.hypothesis_id,
                blueprint_id=candidate.blueprint_id,
                evaluation_id=f"basis.{bundle.robust_promotion.promotion.promotion_id}",
                source_run_id=run_id,
                from_stage=CandidateLifecycleStage.ROBUST_CANDIDATE,
                to_stage=CandidateLifecycleStage.SUBMISSION_READY,
                decision=PromotionDecisionKind.PROMOTE,
                reasons=["autopilot_submission_ready_selected", "packet_selection_top_k"],
                decided_at=promoted_at,
            )
            artifact_records.append(
                SubmissionReadyArtifactRecord(
                    candidate=candidate,
                    robust_promotion=bundle.robust_promotion,
                    submission_promotion=promotion,
                )
            )
            inventory_records.append(
                SubmissionReadyCandidateRecord(
                    inventory_record_id=f"submission_ready.{run_id}.{candidate.candidate_id}",
                    candidate_id=candidate.candidate_id,
                    hypothesis_id=candidate.hypothesis_id,
                    blueprint_id=candidate.blueprint_id,
                    family=bundle.agenda.family,
                    source_run_id=run_id,
                    robust_source_run_id=bundle.robust_promotion.promotion.source_run_id,
                    promotion_id=promotion.promotion_id,
                    validation_ids=bundle.robust_promotion.validation_ids,
                    requested_periods=bundle.robust_promotion.requested_periods,
                    promoted_at=promoted_at,
                    notes="autopilot advanced candidate to submission_ready",
                )
            )
        return artifact_records, inventory_records

    def _build_approved_queue_records(
        self,
        *,
        run_id: str,
        inventory_records: list[SubmissionReadyCandidateRecord],
        review_decisions: list[HumanReviewDecision],
    ) -> list[HumanReviewQueueRecord]:
        decision_by_candidate_id = {
            decision.candidate_id: decision
            for decision in review_decisions
        }
        queue_records: list[HumanReviewQueueRecord] = []
        for record in inventory_records:
            decision = decision_by_candidate_id[record.candidate_id]
            queue_entry_id = f"review_queue.{run_id}.{record.candidate_id}"
            queue_records.append(
                HumanReviewQueueRecord(
                    queue_record_id=f"{queue_entry_id}.approved",
                    queue_entry_id=queue_entry_id,
                    inventory_record_id=record.inventory_record_id,
                    candidate_id=record.candidate_id,
                    hypothesis_id=record.hypothesis_id,
                    blueprint_id=record.blueprint_id,
                    family=record.family,
                    submission_ready_source_run_id=record.source_run_id,
                    status=HumanReviewQueueStatus.APPROVED,
                    source_run_id=decision.source_run_id,
                    priority=0.95,
                    reviewer=decision.reviewer,
                    decision_id=decision.decision_id,
                    created_at=record.promoted_at,
                    updated_at=decision.reviewed_at,
                    notes=decision.notes,
                )
            )
        return queue_records

    def _finalize_packet_flow(
        self,
        *,
        autopilot_run_id: str,
        artifacts_dir: str | Path,
        candidate_pool: dict[str, AutopilotCandidateBundle],
        stopped_reason: AutopilotStopReason,
    ) -> tuple[SubmissionPacketResult | None, list[SubmissionPacketIndexRecord], AutopilotManifest]:
        selected_bundles = self._select_bundles_for_manifest(candidate_pool)
        if not selected_bundles:
            manifest = AutopilotManifest(
                autopilot_run_id=autopilot_run_id,
                generated_at=_utc_now(),
                stopped_reason=stopped_reason,
                target_packet_count=self.settings.autopilot.target_packet_count,
                selected_packet_count=0,
                candidate_ids=[],
                packet_ids=[],
                packet_paths=[],
                review_mode="synthetic_auto_approve",
                selection_policy=(
                    "passing_period_count desc, stage_a_sharpe desc, fitness desc, "
                    "turnover distance to 0.25 asc, candidate_id asc"
                ),
                source_run_ids=[],
            )
            return None, [], manifest

        promote_run_id = _build_run_id("promote", "autopilot")
        promote_started_at = _utc_now()
        self.state_ledger.append_run_state_records(
            [
                self._build_started_run_state(
                    run_id=promote_run_id,
                    run_kind=RunKind.PROMOTE,
                    started_at=promote_started_at,
                    parent_run_id=autopilot_run_id,
                )
            ]
        )
        submission_ready_records, inventory_records = self._build_submission_ready_artifacts(
            run_id=promote_run_id,
            bundles=selected_bundles,
            promoted_at=promote_started_at,
        )
        self.artifact_ledger.write_submission_ready_records(promote_run_id, submission_ready_records)
        submission_ready_by_candidate = {
            record.candidate.candidate_id: record
            for record in submission_ready_records
        }
        submission_ready_stage_records: list[CandidateStageRecord] = []
        for _, group in self._group_bundles_by_context(selected_bundles).items():
            group_records = [
                submission_ready_by_candidate[bundle.candidate_artifact.candidate.candidate_id]
                for bundle in group
            ]
            submission_ready_stage_records.extend(
                _build_submission_ready_stage_records(
                    run_id=promote_run_id,
                    hypothesis=group[0].hypothesis,
                    blueprint=group[0].blueprint,
                    records=group_records,
                )
            )
        self.state_ledger.append_candidate_stage_records(submission_ready_stage_records)
        self.state_ledger.append_submission_ready_records(inventory_records)
        self.state_ledger.append_run_state_records(
            [
                RunStateRecord(
                    run_id=promote_run_id,
                    run_kind=RunKind.PROMOTE,
                    status=RunLifecycleStatus.COMPLETED,
                    started_at=promote_started_at,
                    parent_run_id=autopilot_run_id,
                    completed_at=_utc_now(),
                    candidate_count=len(submission_ready_records),
                )
            ]
        )
        self._refresh_family_analytics(artifacts_dir)

        review_run_id = _build_run_id("review", "autopilot")
        review_started_at = _utc_now()
        self.state_ledger.append_run_state_records(
            [
                self._build_started_run_state(
                    run_id=review_run_id,
                    run_kind=RunKind.REVIEW,
                    started_at=review_started_at,
                    parent_run_id=autopilot_run_id,
                )
            ]
        )
        review_results = []
        for _, group in self._group_bundles_by_context(selected_bundles).items():
            group_submission_ready = [
                submission_ready_by_candidate[bundle.candidate_artifact.candidate.candidate_id]
                for bundle in group
            ]
            review_results.append(
                self.human_review_workflow.run(
                    source_run_id=review_run_id,
                    submission_ready_source_run_id=promote_run_id,
                    hypothesis=group[0].hypothesis,
                    blueprint=group[0].blueprint,
                    submission_ready_records=group_submission_ready,
                    reviewer="autopilot",
                    decision=HumanReviewDecisionKind.APPROVE,
                    reviewed_at=review_started_at,
                    notes="auto_approved_by_autopilot_policy",
                )
            )
        auto_review_records = [
            HumanReviewArtifactRecord(
                submission_ready=outcome.submission_ready,
                review_decision=outcome.review_decision,
            )
            for review_result in review_results
            for outcome in review_result.outcomes
        ]
        self.artifact_ledger.write_human_review_records(review_run_id, auto_review_records)
        self.artifact_ledger.write_auto_review_records(autopilot_run_id, auto_review_records)
        review_decisions = [
            outcome.review_decision
            for review_result in review_results
            for outcome in review_result.outcomes
        ]
        queue_records = self._build_approved_queue_records(
            run_id=promote_run_id,
            inventory_records=inventory_records,
            review_decisions=review_decisions,
        )
        review_stage_records: list[CandidateStageRecord] = []
        for review_result in review_results:
            review_stage_records.extend(
                _build_human_review_stage_records(
                    run_id=review_run_id,
                    hypothesis=review_result.hypothesis,
                    blueprint=review_result.blueprint,
                    review_result=review_result,
                )
            )
        self.state_ledger.append_candidate_stage_records(review_stage_records)
        self.state_ledger.append_human_review_queue_records(queue_records)
        self.state_ledger.append_human_review_decisions(review_decisions)
        reviewed_candidate_ids = [
            outcome.review_decision.candidate_id
            for review_result in review_results
            for outcome in review_result.outcomes
        ]
        self.state_ledger.append_run_state_records(
            [
                RunStateRecord(
                    run_id=review_run_id,
                    run_kind=RunKind.REVIEW,
                    status=RunLifecycleStatus.COMPLETED,
                    started_at=review_started_at,
                    parent_run_id=autopilot_run_id,
                    completed_at=_utc_now(),
                    candidate_count=len(reviewed_candidate_ids),
                )
            ]
        )
        self._refresh_family_analytics(artifacts_dir)

        packet_run_id = _build_run_id("packet", "autopilot")
        packet_started_at = _utc_now()
        self.state_ledger.append_run_state_records(
            [
                self._build_started_run_state(
                    run_id=packet_run_id,
                    run_kind=RunKind.PACKET,
                    started_at=packet_started_at,
                    parent_run_id=autopilot_run_id,
                )
            ]
        )
        packet_results = []
        review_by_candidate = {decision.candidate_id: decision for decision in review_decisions}
        for _, group in self._group_bundles_by_context(selected_bundles).items():
            packet_bundles: list[SubmissionPacketBundle] = []
            for bundle in group:
                candidate_id = bundle.candidate_artifact.candidate.candidate_id
                packet_bundles.append(
                    SubmissionPacketBundle(
                        candidate_artifact=bundle.candidate_artifact,
                        simulation_artifact=bundle.simulation_artifact,
                        evaluation_artifact=bundle.evaluation_artifact,
                        stage_a_promotion=bundle.stage_a_promotion,
                        submission_ready=submission_ready_by_candidate[candidate_id],
                        validation_records=bundle.validation_records,
                        review_decision=review_by_candidate[candidate_id],
                    )
                )
            packet_results.append(
                self.submission_packet_workflow.run(
                    source_run_id=packet_run_id,
                    review_source_run_id=review_run_id,
                    agenda=group[0].agenda,
                    hypothesis=group[0].hypothesis,
                    blueprint=group[0].blueprint,
                    bundles=packet_bundles,
                    generated_at=packet_started_at,
                )
            )
        packet_records: list[SubmissionPacketArtifactRecord] = [
            packet
            for packet_result in packet_results
            for packet in packet_result.packets
        ]
        candidate_ids = [
            candidate_id
            for packet_result in packet_results
            for candidate_id in packet_result.candidate_ids
        ]
        packet_result = SubmissionPacketResult(
            source_run_id=packet_run_id,
            review_source_run_id=review_run_id,
            agenda=packet_results[0].agenda,
            hypothesis=packet_results[0].hypothesis,
            blueprint=packet_results[0].blueprint,
            packets=packet_records,
            candidate_ids=candidate_ids,
        )
        self.artifact_ledger.write_submission_packet_records(packet_run_id, packet_records)
        self.state_ledger.append_run_state_records(
            [
                RunStateRecord(
                    run_id=packet_run_id,
                    run_kind=RunKind.PACKET,
                    status=RunLifecycleStatus.COMPLETED,
                    started_at=packet_started_at,
                    parent_run_id=autopilot_run_id,
                    completed_at=_utc_now(),
                    candidate_count=len(candidate_ids),
                )
            ]
        )

        packet_index_records = self._build_packet_index_updates(
            autopilot_run_id=autopilot_run_id,
            packet_run_id=packet_run_id,
            packet_result=packet_result,
            selected_bundles=selected_bundles,
            artifacts_dir=artifacts_dir,
        )
        packet_paths = [
            str(
                Path(artifacts_dir).expanduser().resolve()
                / "runs"
                / packet_run_id
                / "packets"
                / f"{packet.candidate_artifact.candidate.candidate_id}.json"
            )
            for packet in packet_records
        ]
        source_run_ids = []
        for bundle in selected_bundles:
            for run_id in (
                bundle.stage_a_promotion.promotion.source_run_id,
                bundle.robust_promotion.promotion.source_run_id,
            ):
                if run_id and run_id not in source_run_ids:
                    source_run_ids.append(run_id)
        for run_id in (promote_run_id, review_run_id, packet_run_id):
            if run_id not in source_run_ids:
                source_run_ids.append(run_id)

        manifest = AutopilotManifest(
            autopilot_run_id=autopilot_run_id,
            generated_at=_utc_now(),
            stopped_reason=stopped_reason,
            target_packet_count=self.settings.autopilot.target_packet_count,
            selected_packet_count=len(packet_records),
            candidate_ids=candidate_ids,
            packet_ids=[packet.packet_id for packet in packet_records],
            packet_paths=packet_paths,
            review_mode="synthetic_auto_approve",
            selection_policy=(
                "passing_period_count desc, stage_a_sharpe desc, fitness desc, "
                "turnover distance to 0.25 asc, candidate_id asc"
            ),
            source_run_ids=source_run_ids,
        )
        self._refresh_family_analytics(artifacts_dir)
        return packet_result, packet_index_records, manifest

    def _build_packet_index_updates(
        self,
        *,
        autopilot_run_id: str,
        packet_run_id: str,
        packet_result: SubmissionPacketResult,
        selected_bundles: list[AutopilotCandidateBundle],
        artifacts_dir: str | Path,
    ) -> list[SubmissionPacketIndexRecord]:
        existing_by_signature: dict[str, SubmissionPacketIndexRecord] = {}
        for record in self.state_ledger.load_submission_packet_index_records():
            current = existing_by_signature.get(record.signature)
            if current is None or self._index_rank_key(record) < self._index_rank_key(current):
                existing_by_signature[record.signature] = record

        bundle_by_candidate_id = {
            bundle.candidate_artifact.candidate.candidate_id: bundle
            for bundle in selected_bundles
        }
        updates: list[SubmissionPacketIndexRecord] = []
        for packet in packet_result.packets:
            candidate_id = packet.candidate_artifact.candidate.candidate_id
            bundle = bundle_by_candidate_id[candidate_id]
            signature = candidate_signature(packet.candidate_artifact.candidate)
            record = SubmissionPacketIndexRecord(
                index_entry_id=f"packet_index.{autopilot_run_id}.{candidate_id}",
                autopilot_run_id=autopilot_run_id,
                packet_run_id=packet_run_id,
                candidate_id=candidate_id,
                family=packet.hypothesis.family,
                signature=signature,
                packet_id=packet.packet_id,
                packet_path=str(
                    Path(artifacts_dir).expanduser().resolve()
                    / "runs"
                    / packet_run_id
                    / "packets"
                    / f"{candidate_id}.json"
                ),
                source_run_ids=[
                    bundle.stage_a_promotion.promotion.source_run_id,
                    bundle.robust_promotion.promotion.source_run_id,
                    packet.submission_ready.submission_promotion.source_run_id,
                    packet.review_decision.source_run_id,
                    packet.source_run_id,
                ],
                passing_period_count=len(bundle.robust_promotion.passing_periods),
                stage_a_sharpe=bundle.evaluation_artifact.evaluation.sharpe,
                fitness=bundle.evaluation_artifact.evaluation.fitness,
                turnover=bundle.evaluation_artifact.evaluation.turnover,
                recorded_at=packet.generated_at,
            )
            current = existing_by_signature.get(signature)
            if current is None or self._index_rank_key(record) < self._index_rank_key(current):
                updates.append(record)
                existing_by_signature[signature] = record
        return updates

    @staticmethod
    def _build_started_run_state(
        *,
        run_id: str,
        run_kind: RunKind,
        started_at: datetime,
        parent_run_id: str | None,
    ) -> RunStateRecord:
        return RunStateRecord(
            run_id=run_id,
            run_kind=run_kind,
            status=RunLifecycleStatus.STARTED,
            started_at=started_at,
            parent_run_id=parent_run_id,
        )
