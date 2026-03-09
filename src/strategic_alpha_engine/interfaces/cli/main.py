from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from strategic_alpha_engine.application.contracts import (
    AgendaQueueRecord,
    CandidateStageRecord,
    FamilyLearnerSummary,
    FamilyStatsSnapshot,
    RunStateRecord,
    ValidationBacklogEntry,
)
from strategic_alpha_engine.application.services import (
    FamilyWeightedAgendaPrioritizer,
    FamilyAnalyticsBundle,
    HeuristicResearchAgendaManager,
    HeuristicSearchPolicyLearner,
    LocalArtifactFamilyAnalyticsBuilder,
    MetadataBackedStaticValidator,
    RuleBasedStrategicCritic,
    RuleBasedStageAEvaluator,
    RuleBasedStageAPromotionDecider,
    RuleBasedValidationRunner,
    SkeletonCandidateSynthesizer,
    StaticBlueprintBuilder,
    StaticHypothesisPlanner,
)
from strategic_alpha_engine.application.workflows import (
    PlanWorkflow,
    ResearchOnceWorkflow,
    SimulationExecutionPolicy,
    SimulationOrchestratorWorkflow,
    StageAEvaluationWorkflow,
    SynthesizeWorkflow,
    ValidateWorkflow,
)
from strategic_alpha_engine.config import RuntimeSettings, load_runtime_settings
from strategic_alpha_engine.domain import (
    CritiqueReport,
    ExpressionCandidate,
    HypothesisSpec,
    SignalBlueprint,
    ResearchAgenda,
    StaticValidationReport,
    ValidationRecord,
    build_sample_critique_report,
    build_sample_expression_candidate,
    build_sample_hypothesis_spec,
    build_sample_research_agenda,
    build_sample_research_agenda_pool,
    build_sample_signal_blueprint,
    build_sample_validation_record,
)
from strategic_alpha_engine.domain.enums import (
    CandidateLifecycleStage,
    FieldClass,
    ResearchHorizon,
    RunKind,
    RunLifecycleStatus,
    SimulationStatus,
    ValidationBacklogStatus,
    ValidationStage,
)
from strategic_alpha_engine.infrastructure.artifacts import LocalFileArtifactLedger
from strategic_alpha_engine.infrastructure.brain import FakeBrainSimulationClient
from strategic_alpha_engine.infrastructure.metadata import load_seed_metadata_catalog
from strategic_alpha_engine.infrastructure.state import LocalFileStateLedger
from strategic_alpha_engine.prompts import load_prompt_asset, load_prompt_golden_sample


def _write_output(payload: dict | list, output_path: str | None) -> None:
    rendered = json.dumps(payload, indent=2)
    if not output_path:
        print(rendered)
        return
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered + "\n", encoding="utf-8")


def _read_input_payload(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_jsonl_file(path: Path) -> list[dict]:
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []
    return [json.loads(line) for line in content.splitlines()]


def _load_agenda(path: str | None) -> ResearchAgenda:
    if not path:
        return build_sample_research_agenda()
    return ResearchAgenda(**_read_input_payload(path))


def _load_agendas(paths: list[str] | None) -> list[ResearchAgenda]:
    if not paths:
        return []
    return [_load_agenda(path) for path in paths]


def _load_seed_agendas(paths: list[str] | None) -> list[ResearchAgenda]:
    agendas = _load_agendas(paths)
    if agendas:
        return agendas
    return build_sample_research_agenda_pool()


def _load_hypothesis(path: str | None) -> HypothesisSpec:
    if not path:
        return build_sample_hypothesis_spec()
    return HypothesisSpec(**_read_input_payload(path))


def _load_blueprint(path: str | None) -> SignalBlueprint:
    if not path:
        return build_sample_signal_blueprint()
    return SignalBlueprint(**_read_input_payload(path))


def _build_static_validator() -> MetadataBackedStaticValidator:
    return MetadataBackedStaticValidator(load_seed_metadata_catalog())


def _build_plan_workflow() -> PlanWorkflow:
    return PlanWorkflow(
        hypothesis_planner=StaticHypothesisPlanner(),
        blueprint_builder=StaticBlueprintBuilder(),
    )


def _build_synthesize_workflow() -> SynthesizeWorkflow:
    return SynthesizeWorkflow(
        candidate_synthesizer=SkeletonCandidateSynthesizer(),
        static_validator=_build_static_validator(),
        strategic_critic=RuleBasedStrategicCritic(),
    )


def _build_stage_a_workflow() -> StageAEvaluationWorkflow:
    return StageAEvaluationWorkflow(
        evaluator=RuleBasedStageAEvaluator(),
        promotion_decider=RuleBasedStageAPromotionDecider(),
    )


def _build_validate_workflow(*, base_time: datetime | None = None) -> ValidateWorkflow:
    return ValidateWorkflow(
        validation_runner=RuleBasedValidationRunner(base_time=base_time),
    )


def _load_synthesize_inputs(
    plan_input_path: str | None,
    hypothesis_input_path: str | None,
    blueprint_input_path: str | None,
) -> tuple[HypothesisSpec, SignalBlueprint]:
    if plan_input_path:
        payload = _read_input_payload(plan_input_path)
        return HypothesisSpec(**payload["hypothesis"]), SignalBlueprint(**payload["blueprint"])
    return _load_hypothesis(hypothesis_input_path), _load_blueprint(blueprint_input_path)


def _load_simulate_inputs(
    agenda_input_path: str | None,
    plan_input_path: str | None,
    hypothesis_input_path: str | None,
    blueprint_input_path: str | None,
) -> tuple[ResearchAgenda | None, HypothesisSpec, SignalBlueprint]:
    if plan_input_path:
        payload = _read_input_payload(plan_input_path)
        agenda_payload = payload.get("agenda")
        agenda = ResearchAgenda(**agenda_payload) if agenda_payload is not None else None
        return agenda, HypothesisSpec(**payload["hypothesis"]), SignalBlueprint(**payload["blueprint"])
    if hypothesis_input_path or blueprint_input_path:
        return None, _load_hypothesis(hypothesis_input_path), _load_blueprint(blueprint_input_path)
    agenda = _load_agenda(agenda_input_path)
    plan_result = _build_plan_workflow().run(agenda)
    return plan_result.agenda, plan_result.hypothesis, plan_result.blueprint


def _build_simulation_policy(
    settings: RuntimeSettings,
    hypothesis: HypothesisSpec,
) -> SimulationExecutionPolicy:
    return SimulationExecutionPolicy(
        region=hypothesis.target_region or settings.region,
        universe=hypothesis.target_universe or settings.universe,
        delay=settings.simulation_delay,
        neutralization=settings.simulation_neutralization,
        test_period=settings.default_test_period,
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _build_run_id(prefix: str, family: str) -> str:
    timestamp = _utc_now().strftime("%Y%m%dT%H%M%S%fZ")
    return f"{prefix}.{family}.{timestamp}"


def _latest_candidate_stage_records(
    records: list[CandidateStageRecord],
) -> dict[str, CandidateStageRecord]:
    latest: dict[str, CandidateStageRecord] = {}
    for record in records:
        latest[record.candidate_id] = record
    return latest


def _latest_run_state_records(records: list[RunStateRecord]) -> dict[str, RunStateRecord]:
    latest: dict[str, RunStateRecord] = {}
    for record in records:
        latest[record.run_id] = record
    return latest


def _build_family_analytics_bundle(
    root_dir: str | Path,
    candidate_stage_records: list[CandidateStageRecord],
) -> FamilyAnalyticsBundle:
    return LocalArtifactFamilyAnalyticsBuilder().build(
        root_dir,
        candidate_stage_records=candidate_stage_records,
    )


def _build_family_policy_recommendations(
    learner_summaries: list[FamilyLearnerSummary],
):
    return HeuristicSearchPolicyLearner().recommend(learner_summaries)


def _build_agenda_priority_recommendations(
    agendas: list[ResearchAgenda],
    family_recommendations,
):
    if not agendas:
        return []
    return FamilyWeightedAgendaPrioritizer().prioritize(
        agendas,
        family_recommendations,
    )


def _build_agenda_selection(
    agendas: list[ResearchAgenda],
    family_recommendations,
    *,
    excluded_agenda_ids: set[str] | None = None,
):
    return HeuristicResearchAgendaManager(
        agenda_prioritizer=FamilyWeightedAgendaPrioritizer(),
    ).select_next(
        agendas,
        family_recommendations,
        excluded_agenda_ids=excluded_agenda_ids,
    )


def _build_candidate_stage_records(
    *,
    run_id: str,
    hypothesis: HypothesisSpec,
    synthesize_result,
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

        final_stage = outcome.promotion.to_stage
        note = f"promotion decision: {outcome.promotion.decision}"
        stage_records.append(
            CandidateStageRecord(
                stage_record_id=f"stage.{run_id}.{candidate_id}.{final_stage}",
                candidate_id=candidate_id,
                hypothesis_id=hypothesis.hypothesis_id,
                blueprint_id=synthesize_result.blueprint.blueprint_id,
                family=hypothesis.family,
                stage=final_stage,
                source_run_id=run_id,
                recorded_at=outcome.promotion.decided_at,
                notes=note[:240],
            )
        )

    return stage_records


def _build_stage_counts(candidate_stage_records: list[CandidateStageRecord]) -> dict[str, int]:
    counts = {stage.value: 0 for stage in CandidateLifecycleStage}
    for record in _latest_candidate_stage_records(candidate_stage_records).values():
        counts[record.stage] += 1
    return counts


def _resolve_validate_source_run_id(
    state_ledger: LocalFileStateLedger,
    explicit_run_id: str | None,
) -> str:
    if explicit_run_id:
        return explicit_run_id

    latest_run_records = list(_latest_run_state_records(state_ledger.load_run_state_records()).values())
    latest_run_records.sort(
        key=lambda record: record.completed_at or record.started_at,
        reverse=True,
    )
    for record in latest_run_records:
        if record.run_kind in {RunKind.SIMULATE, RunKind.RESEARCH_LOOP}:
            return record.run_id
    raise ValueError("No simulate or research_loop run is available for validation")


def _load_validate_inputs(
    root_dir: str | Path,
    state_ledger: LocalFileStateLedger,
    source_candidate_run_id: str,
    candidate_ids: list[str] | None,
) -> tuple[ResearchAgenda | None, HypothesisSpec, SignalBlueprint, list[ExpressionCandidate]]:
    artifacts_root = Path(root_dir).expanduser().resolve()
    context = _load_run_context(artifacts_root, source_candidate_run_id)
    hypothesis_payload = context["hypothesis"]
    blueprint_payload = context["blueprint"]
    if hypothesis_payload is None or blueprint_payload is None:
        raise ValueError("validation source run must have hypothesis and blueprint context")

    candidates_path = artifacts_root / "runs" / source_candidate_run_id / "candidates.jsonl"
    candidate_fields = set(ExpressionCandidate.model_fields)
    candidates = [
        ExpressionCandidate(**{key: value for key, value in payload.items() if key in candidate_fields})
        for payload in _read_jsonl_file(candidates_path)
    ]
    if not candidates:
        raise ValueError("validation source run must include candidate artifacts")

    eligible_candidate_ids = {
        record.candidate_id
        for record in state_ledger.load_candidate_stage_records()
        if record.source_run_id == source_candidate_run_id and record.stage == CandidateLifecycleStage.SIM_PASSED
    }
    requested_candidate_ids = set(candidate_ids or [])
    if requested_candidate_ids:
        eligible_candidate_ids &= requested_candidate_ids

    selected_candidates = [
        candidate
        for candidate in candidates
        if candidate.candidate_id in eligible_candidate_ids
    ]
    if not selected_candidates:
        raise ValueError("No sim_passed candidates are available for validation from the selected run")

    agenda = ResearchAgenda(**context["agenda"]) if context["agenda"] is not None else None
    return (
        agenda,
        HypothesisSpec(**hypothesis_payload),
        SignalBlueprint(**blueprint_payload),
        selected_candidates,
    )


def _build_validation_backlog_entries(
    *,
    run_id: str,
    candidates: list[ExpressionCandidate],
    family: str,
    validation_stage: ValidationStage,
    period: str,
    created_at: datetime,
    status: ValidationBacklogStatus,
    updated_at: datetime | None = None,
) -> list[ValidationBacklogEntry]:
    entries: list[ValidationBacklogEntry] = []
    priority = 0.85 if validation_stage == ValidationStage.STAGE_B else 0.7
    for candidate in candidates:
        entries.append(
            ValidationBacklogEntry(
                backlog_entry_id=(
                    f"backlog.{run_id}.{candidate.candidate_id}.{validation_stage.value}.{period}.{status.value}"
                ),
                candidate_id=candidate.candidate_id,
                family=family,
                requested_period=period,
                validation_stage=validation_stage.value,
                priority=priority,
                status=status,
                source_run_id=run_id,
                created_at=created_at,
                updated_at=updated_at,
            )
        )
    return entries


def _latest_validation_backlog_entries(
    entries: list[ValidationBacklogEntry],
) -> list[ValidationBacklogEntry]:
    latest: dict[tuple[str, str, str], ValidationBacklogEntry] = {}
    for entry in entries:
        key = (
            entry.candidate_id,
            entry.validation_stage,
            entry.requested_period,
        )
        current = latest.get(key)
        current_timestamp = (current.updated_at or current.created_at) if current is not None else None
        entry_timestamp = entry.updated_at or entry.created_at
        if current_timestamp is None or entry_timestamp >= current_timestamp:
            latest[key] = entry
    return list(latest.values())


def _load_validation_records(
    root_dir: str | Path,
    run_state_records: list[RunStateRecord],
) -> list[ValidationRecord]:
    artifacts_root = Path(root_dir).expanduser().resolve()
    validation_records: list[ValidationRecord] = []
    for record in _latest_run_state_records(run_state_records).values():
        if record.run_kind != RunKind.VALIDATE:
            continue
        validations_path = artifacts_root / "runs" / record.run_id / "validations.jsonl"
        for payload in _read_jsonl_file(validations_path):
            validation_payload = payload.get("validation")
            if validation_payload is None:
                continue
            validation_records.append(ValidationRecord(**validation_payload))
    return validation_records


def _build_validation_summary(validation_records: list[ValidationRecord]) -> dict:
    if not validation_records:
        return {
            "total_records": 0,
            "passed_records": 0,
            "failed_records": 0,
            "counts_by_stage": {},
            "counts_by_period": {},
            "latest_run_id": None,
        }

    counts_by_stage: Counter[str] = Counter(
        record.validation_stage
        for record in validation_records
    )
    counts_by_period: Counter[str] = Counter(
        record.period
        for record in validation_records
    )
    latest_record = max(validation_records, key=lambda record: record.validated_at)
    passed_records = sum(1 for record in validation_records if record.pass_decision)

    return {
        "total_records": len(validation_records),
        "passed_records": passed_records,
        "failed_records": len(validation_records) - passed_records,
        "counts_by_stage": dict(sorted(counts_by_stage.items())),
        "counts_by_period": dict(sorted(counts_by_period.items())),
        "latest_run_id": latest_record.source_run_id,
    }


def _build_simulation_status_counts(simulation_result) -> dict[str, int]:
    counts = {
        status.value: 0
        for status in (
            SimulationStatus.SUCCEEDED,
            SimulationStatus.FAILED,
            SimulationStatus.TIMED_OUT,
        )
    }
    for execution in simulation_result.executions:
        counts[execution.result.status] += 1
    return counts


def _resolve_family_analytics(
    root_dir: str | Path,
    state_ledger: LocalFileStateLedger,
) -> tuple[list[FamilyStatsSnapshot], list[FamilyLearnerSummary]]:
    candidate_stage_records = state_ledger.load_candidate_stage_records()
    family_stats = state_ledger.load_family_stats()
    learner_summaries = state_ledger.load_family_learner_summaries()
    if family_stats and learner_summaries:
        return family_stats, learner_summaries
    analytics_bundle = _build_family_analytics_bundle(root_dir, candidate_stage_records)
    if not family_stats:
        family_stats = analytics_bundle.family_stats
    if not learner_summaries:
        learner_summaries = analytics_bundle.learner_summaries
    return family_stats, learner_summaries


def _build_agenda_queue_records(
    *,
    run_id: str,
    iteration_index: int,
    agendas: list[ResearchAgenda],
    agenda_recommendations,
    selected_agenda_id: str | None,
    recorded_at: datetime,
) -> list[AgendaQueueRecord]:
    agendas_by_id = {
        agenda.agenda_id: agenda
        for agenda in agendas
    }
    records: list[AgendaQueueRecord] = []
    for rank, recommendation in enumerate(agenda_recommendations, start=1):
        agenda = agendas_by_id[recommendation.agenda_id]
        records.append(
            AgendaQueueRecord(
                queue_record_id=f"queue.{run_id}.{rank:03d}",
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


def _build_agenda_queue_summary(agenda_queue_records: list[AgendaQueueRecord]) -> dict:
    if not agenda_queue_records:
        return {
            "latest_source_run_id": None,
            "iteration_index": None,
            "selected_agenda_id": None,
            "total_entries": 0,
            "entries": [],
        }

    latest_record_by_run_id: dict[str, datetime] = {}
    for record in agenda_queue_records:
        current_latest = latest_record_by_run_id.get(record.source_run_id)
        if current_latest is None or record.recorded_at > current_latest:
            latest_record_by_run_id[record.source_run_id] = record.recorded_at

    latest_source_run_id = max(
        latest_record_by_run_id,
        key=lambda run_id: latest_record_by_run_id[run_id],
    )
    latest_snapshot = [
        record
        for record in agenda_queue_records
        if record.source_run_id == latest_source_run_id
    ]
    latest_snapshot.sort(key=lambda record: record.rank)
    selected_record = next(
        (record for record in latest_snapshot if record.selected_for_execution),
        None,
    )

    return {
        "latest_source_run_id": latest_source_run_id,
        "iteration_index": latest_snapshot[0].iteration_index if latest_snapshot else None,
        "selected_agenda_id": selected_record.agenda_id if selected_record is not None else None,
        "total_entries": len(latest_snapshot),
        "entries": [record.model_dump(mode="json") for record in latest_snapshot[:5]],
    }


def _load_run_context(root_dir: Path, run_id: str) -> dict[str, dict | None]:
    run_dir = root_dir / "runs" / run_id
    context: dict[str, dict | None] = {}
    for name in ("agenda", "hypothesis", "blueprint"):
        path = run_dir / f"{name}.json"
        context[name] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    return context


def _build_status_summary(root_dir: str | Path) -> dict:
    artifacts_root = Path(root_dir).expanduser().resolve()
    state_ledger = LocalFileStateLedger(artifacts_root)
    candidate_stage_records = state_ledger.load_candidate_stage_records()
    run_state_records = state_ledger.load_run_state_records()
    agenda_queue_records = state_ledger.load_agenda_queue_records()
    family_stats = state_ledger.load_family_stats()
    learner_summaries = state_ledger.load_family_learner_summaries()
    validation_backlog_entries = state_ledger.load_validation_backlog_entries()
    latest_validation_backlog_entries = _latest_validation_backlog_entries(validation_backlog_entries)
    validation_records = _load_validation_records(artifacts_root, run_state_records)

    if not family_stats or not learner_summaries:
        analytics_bundle = _build_family_analytics_bundle(artifacts_root, candidate_stage_records)
        if not family_stats:
            family_stats = analytics_bundle.family_stats
        if not learner_summaries:
            learner_summaries = analytics_bundle.learner_summaries
    family_recommendations = _build_family_policy_recommendations(learner_summaries)

    latest_run_records = list(_latest_run_state_records(run_state_records).values())
    latest_run_records.sort(
        key=lambda record: record.completed_at or record.started_at,
        reverse=True,
    )

    run_counts_by_kind = {run_kind.value: 0 for run_kind in RunKind}
    run_counts_by_status = {status.value: 0 for status in RunLifecycleStatus}
    for record in latest_run_records:
        run_counts_by_kind[record.run_kind] += 1
        run_counts_by_status[record.status] += 1

    recent_24h_cutoff = _utc_now() - timedelta(hours=24)
    recent_stage_records = [
        record
        for record in candidate_stage_records
        if record.recorded_at >= recent_24h_cutoff
    ]
    recent_stage_counts = {stage.value: 0 for stage in CandidateLifecycleStage}
    recent_family_counts: Counter[str] = Counter()
    for record in recent_stage_records:
        recent_stage_counts[record.stage] += 1
        recent_family_counts[record.family] += 1

    backlog_counts: Counter[str] = Counter(entry.status for entry in latest_validation_backlog_entries)

    research_loop_records = [
        record
        for record in latest_run_records
        if record.run_kind == RunKind.RESEARCH_LOOP
    ]
    running_loop_records = [
        record
        for record in research_loop_records
        if record.status == RunLifecycleStatus.STARTED
    ]
    if running_loop_records:
        loop_status = {
            "current_state": "running",
            "active_run_ids": [record.run_id for record in running_loop_records],
        }
    elif research_loop_records:
        loop_status = {
            "current_state": "idle",
            "active_run_ids": [],
            "last_run_id": research_loop_records[0].run_id,
            "last_completed_at": research_loop_records[0].completed_at.isoformat()
            if research_loop_records[0].completed_at
            else None,
        }
    else:
        loop_status = {
            "current_state": "not_started",
            "active_run_ids": [],
        }

    latest_context = None
    if latest_run_records:
        latest_record = latest_run_records[0]
        latest_context = _load_run_context(artifacts_root, latest_record.run_id)
        agenda_status = {
            "latest_run_id": latest_record.run_id,
            "latest_run_kind": latest_record.run_kind,
            "latest_family": (
                (latest_context["hypothesis"] or {}).get("family")
                or (latest_context["agenda"] or {}).get("family")
            ),
            "latest_agenda_id": (
                (latest_context["agenda"] or {}).get("agenda_id")
                or (latest_context["hypothesis"] or {}).get("agenda_id")
            ),
            "latest_hypothesis_id": (latest_context["hypothesis"] or {}).get("hypothesis_id"),
            "latest_blueprint_id": (latest_context["blueprint"] or {}).get("blueprint_id"),
        }
    else:
        agenda_status = {
            "latest_run_id": None,
            "latest_run_kind": None,
            "latest_family": None,
            "latest_agenda_id": None,
            "latest_hypothesis_id": None,
            "latest_blueprint_id": None,
        }

    return {
        "generated_at": _utc_now().isoformat(),
        "artifacts_root": str(artifacts_root),
        "loop_status": loop_status,
        "agenda_status": agenda_status,
        "family_stats": [snapshot.model_dump(mode="json") for snapshot in family_stats],
        "family_learner_summaries": [
            summary.model_dump(mode="json")
            for summary in learner_summaries
        ],
        "learner_recommendations": [
            recommendation.model_dump(mode="json")
            for recommendation in family_recommendations
        ],
        "validation_backlog": {
            "total_entries": len(latest_validation_backlog_entries),
            "counts_by_status": dict(sorted(backlog_counts.items())),
        },
        "validation_summary": _build_validation_summary(validation_records),
        "agenda_queue": _build_agenda_queue_summary(agenda_queue_records),
        "candidate_stage_counts": _build_stage_counts(candidate_stage_records),
        "recent_candidate_flow_24h": {
            "cutoff": recent_24h_cutoff.isoformat(),
            "event_count": len(recent_stage_records),
            "counts_by_stage": recent_stage_counts,
            "counts_by_family": dict(sorted(recent_family_counts.items())),
        },
        "runs": {
            "total_runs": len(latest_run_records),
            "counts_by_kind": run_counts_by_kind,
            "counts_by_status": run_counts_by_status,
            "recent_run_ids": [record.run_id for record in latest_run_records[:5]],
        },
    }


def _execute_local_research_run(
    *,
    run_id: str,
    run_kind: RunKind,
    settings: RuntimeSettings,
    state_ledger: LocalFileStateLedger,
    artifacts_dir: str,
    agenda: ResearchAgenda | None,
    hypothesis: HypothesisSpec,
    blueprint: SignalBlueprint,
    fake_terminal_status: str,
    max_polls: int | None,
) -> dict:
    started_at = _utc_now()
    state_ledger.append_run_state_records(
        [
            RunStateRecord(
                run_id=run_id,
                run_kind=run_kind,
                status=RunLifecycleStatus.STARTED,
                started_at=started_at,
            )
        ]
    )

    try:
        synthesize_result = _build_synthesize_workflow().run(hypothesis=hypothesis, blueprint=blueprint)
        policy = _build_simulation_policy(settings, hypothesis)
        resolved_max_polls = max_polls or (settings.brain.max_polls if settings.brain else 3)
        simulation_result = SimulationOrchestratorWorkflow(
            brain_client=FakeBrainSimulationClient(
                terminal_status=SimulationStatus(fake_terminal_status),
                base_time=started_at - timedelta(minutes=5),
            ),
            max_polls=resolved_max_polls,
        ).run(
            synthesize_result=synthesize_result,
            policy=policy,
        )
        stage_a_result = _build_stage_a_workflow().run(
            simulation_result,
            source_run_id=run_id,
        )

        artifact_ledger = LocalFileArtifactLedger(artifacts_dir)
        artifact_run_dir = artifact_ledger.write_synthesize_result(
            run_id,
            synthesize_result,
            agenda=agenda,
        )
        artifact_ledger.write_simulation_result(run_id, simulation_result)
        artifact_ledger.write_stage_a_result(run_id, stage_a_result)

        candidate_stage_records = _build_candidate_stage_records(
            run_id=run_id,
            hypothesis=hypothesis,
            synthesize_result=synthesize_result,
            stage_a_result=stage_a_result,
            default_recorded_at=started_at,
        )
        state_ledger.append_candidate_stage_records(candidate_stage_records)
        all_stage_records = state_ledger.load_candidate_stage_records()
        analytics_bundle = _build_family_analytics_bundle(artifacts_dir, all_stage_records)
        family_stats = analytics_bundle.family_stats
        learner_summaries = analytics_bundle.learner_summaries
        state_ledger.write_family_stats(family_stats)
        state_ledger.write_family_learner_summaries(learner_summaries)

        completed_at = _utc_now()
        state_ledger.append_run_state_records(
            [
                RunStateRecord(
                    run_id=run_id,
                    run_kind=run_kind,
                    status=RunLifecycleStatus.COMPLETED,
                    started_at=started_at,
                    completed_at=completed_at,
                    candidate_count=len(synthesize_result.evaluations),
                    accepted_candidate_count=len(synthesize_result.accepted_candidate_ids),
                    simulated_candidate_count=len(simulation_result.simulated_candidate_ids),
                )
            ]
        )

        family_snapshot = next(
            (
                snapshot.model_dump(mode="json")
                for snapshot in family_stats
                if snapshot.family == hypothesis.family
            ),
            None,
        )
        learner_summary = next(
            (
                summary.model_dump(mode="json")
                for summary in learner_summaries
                if summary.family == hypothesis.family
            ),
            None,
        )
        return {
            "run_id": run_id,
            "family": hypothesis.family,
            "agenda_id": agenda.agenda_id if agenda is not None else hypothesis.agenda_id,
            "hypothesis_id": hypothesis.hypothesis_id,
            "blueprint_id": blueprint.blueprint_id,
            "policy": policy.model_dump(mode="json"),
            "accepted_candidate_ids": synthesize_result.accepted_candidate_ids,
            "rejected_candidate_ids": synthesize_result.rejected_candidate_ids,
            "simulated_candidate_ids": simulation_result.simulated_candidate_ids,
            "promoted_candidate_ids": stage_a_result.promoted_candidate_ids,
            "stage_a_rejected_candidate_ids": stage_a_result.rejected_candidate_ids,
            "skipped_candidate_ids": simulation_result.skipped_candidate_ids,
            "simulation_status_counts": _build_simulation_status_counts(simulation_result),
            "artifact_run_dir": str(artifact_run_dir),
            "state_dir": str(state_ledger.state_directory()),
            "family_stats": family_snapshot,
            "family_learner_summary": learner_summary,
        }
    except Exception as exc:
        state_ledger.append_run_state_records(
            [
                RunStateRecord(
                    run_id=run_id,
                    run_kind=run_kind,
                    status=RunLifecycleStatus.FAILED,
                    started_at=started_at,
                    completed_at=_utc_now(),
                    error_message=str(exc)[:300],
                )
            ]
        )
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Strategic Alpha Engine developer CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    schema_parser = subparsers.add_parser("schema", help="Print JSON schema for a model")
    schema_parser.add_argument(
        "--model",
        choices=["agenda", "hypothesis", "blueprint", "candidate", "critique", "static_validation", "validation"],
        required=True,
    )
    schema_parser.add_argument("--out", default=None)

    example_parser = subparsers.add_parser("example", help="Print example payload for a model")
    example_parser.add_argument(
        "--model",
        choices=["agenda", "hypothesis", "blueprint", "candidate", "critique", "static_validation", "validation"],
        required=True,
    )
    example_parser.add_argument("--out", default=None)

    research_once_parser = subparsers.add_parser(
        "research-once",
        help="Run the static structured-generation workflow once and print the result",
    )
    research_once_parser.add_argument("--out", default=None)

    plan_parser = subparsers.add_parser(
        "plan",
        help="Run agenda -> hypothesis -> blueprint planning and print the result",
    )
    plan_parser.add_argument("--agenda-in", default=None)
    plan_parser.add_argument("--out", default=None)

    synthesize_parser = subparsers.add_parser(
        "synthesize",
        help="Run blueprint -> candidate -> validation -> critique synthesis and print the result",
    )
    synthesize_parser.add_argument("--plan-in", default=None)
    synthesize_parser.add_argument("--hypothesis-in", default=None)
    synthesize_parser.add_argument("--blueprint-in", default=None)
    synthesize_parser.add_argument("--out", default=None)

    simulate_parser = subparsers.add_parser(
        "simulate",
        help="Run synthesis and simulation for critique-passed candidates and persist local ledgers",
    )
    simulate_parser.add_argument("--agenda-in", default=None)
    simulate_parser.add_argument("--plan-in", default=None)
    simulate_parser.add_argument("--hypothesis-in", default=None)
    simulate_parser.add_argument("--blueprint-in", default=None)
    simulate_parser.add_argument("--settings-dir", default=None)
    simulate_parser.add_argument("--artifacts-dir", default="artifacts")
    simulate_parser.add_argument("--run-id", default=None)
    simulate_parser.add_argument(
        "--fake-terminal-status",
        choices=[
            SimulationStatus.SUCCEEDED.value,
            SimulationStatus.FAILED.value,
            SimulationStatus.TIMED_OUT.value,
        ],
        default=SimulationStatus.SUCCEEDED.value,
    )
    simulate_parser.add_argument("--max-polls", type=int, default=None)
    simulate_parser.add_argument("--out", default=None)

    research_loop_parser = subparsers.add_parser(
        "research-loop",
        help="Run a bounded research loop over prioritized agendas and persist local ledgers",
    )
    research_loop_parser.add_argument("--settings-dir", default=None)
    research_loop_parser.add_argument("--artifacts-dir", default="artifacts")
    research_loop_parser.add_argument("--agenda-in", action="append", default=None)
    research_loop_parser.add_argument("--iterations", type=int, default=1)
    research_loop_parser.add_argument(
        "--fake-terminal-status",
        choices=[
            SimulationStatus.SUCCEEDED.value,
            SimulationStatus.FAILED.value,
            SimulationStatus.TIMED_OUT.value,
        ],
        default=SimulationStatus.SUCCEEDED.value,
    )
    research_loop_parser.add_argument("--max-polls", type=int, default=None)
    research_loop_parser.add_argument("--out", default=None)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Run a rule-based validation pass for sim_passed candidates from a prior run",
    )
    validate_parser.add_argument("--artifacts-dir", default="artifacts")
    validate_parser.add_argument("--source-run-id", default=None)
    validate_parser.add_argument("--candidate-id", action="append", default=None)
    validate_parser.add_argument(
        "--validation-stage",
        choices=[ValidationStage.STAGE_B.value, ValidationStage.STAGE_C.value],
        default=ValidationStage.STAGE_B.value,
    )
    validate_parser.add_argument("--period", default="P3Y0M0D")
    validate_parser.add_argument("--out", default=None)

    status_parser = subparsers.add_parser("status", help="Summarize local artifact and state ledgers")
    status_parser.add_argument("--artifacts-dir", default="artifacts")
    status_parser.add_argument("--out", default=None)

    policy_parser = subparsers.add_parser(
        "policy",
        help="Rank families from learner summaries and optionally weight agenda priorities",
    )
    policy_parser.add_argument("--artifacts-dir", default="artifacts")
    policy_parser.add_argument("--agenda-in", action="append", default=None)
    policy_parser.add_argument("--out", default=None)

    config_parser = subparsers.add_parser("config", help="Load and print runtime settings")
    config_parser.add_argument("--settings-dir", default=None)
    config_parser.add_argument("--require-llm", action="store_true")
    config_parser.add_argument("--require-brain", action="store_true")
    config_parser.add_argument("--out", default=None)

    catalog_parser = subparsers.add_parser("catalog", help="Inspect seeded metadata catalog")
    catalog_parser.add_argument("--view", choices=["summary", "fields", "operators"], default="summary")
    catalog_parser.add_argument("--field-class", choices=[field_class.value for field_class in FieldClass])
    catalog_parser.add_argument("--horizon", choices=[horizon.value for horizon in ResearchHorizon])
    catalog_parser.add_argument("--limit", type=int, default=10)
    catalog_parser.add_argument("--out", default=None)

    prompt_parser = subparsers.add_parser("prompt", help="Inspect prompt assets and golden samples")
    prompt_parser.add_argument("--role", choices=["planner", "blueprint", "critic"], required=True)
    prompt_parser.add_argument("--sample-id", default=None)
    prompt_parser.add_argument("--out", default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "schema":
        schema_map = {
            "agenda": ResearchAgenda.model_json_schema(),
            "hypothesis": HypothesisSpec.model_json_schema(),
            "blueprint": SignalBlueprint.model_json_schema(),
            "candidate": ExpressionCandidate.model_json_schema(),
            "critique": CritiqueReport.model_json_schema(),
            "static_validation": StaticValidationReport.model_json_schema(),
            "validation": ValidationRecord.model_json_schema(),
        }
        payload = schema_map[args.model]
        _write_output(payload, args.out)
        return 0

    if args.command == "example":
        example_map = {
            "agenda": build_sample_research_agenda().model_dump(),
            "hypothesis": build_sample_hypothesis_spec().model_dump(),
            "blueprint": build_sample_signal_blueprint().model_dump(),
            "candidate": build_sample_expression_candidate().model_dump(),
            "critique": build_sample_critique_report().model_dump(),
            "static_validation": MetadataBackedStaticValidator(
                load_seed_metadata_catalog()
            ).validate(
                build_sample_signal_blueprint(),
                build_sample_expression_candidate(),
            ).model_dump(),
            "validation": build_sample_validation_record().model_dump(mode="json"),
        }
        payload = example_map[args.model]
        _write_output(payload, args.out)
        return 0

    if args.command == "research-once":
        workflow = ResearchOnceWorkflow(
            hypothesis_planner=StaticHypothesisPlanner(),
            blueprint_builder=StaticBlueprintBuilder(),
            candidate_synthesizer=SkeletonCandidateSynthesizer(),
            static_validator=_build_static_validator(),
            strategic_critic=RuleBasedStrategicCritic(),
        )
        result = workflow.run(build_sample_research_agenda())
        payload = result.model_dump()
        _write_output(payload, args.out)
        return 0

    if args.command == "plan":
        agenda = _load_agenda(args.agenda_in)
        result = _build_plan_workflow().run(agenda)
        _write_output(result.model_dump(mode="json"), args.out)
        return 0

    if args.command == "synthesize":
        hypothesis, blueprint = _load_synthesize_inputs(
            plan_input_path=args.plan_in,
            hypothesis_input_path=args.hypothesis_in,
            blueprint_input_path=args.blueprint_in,
        )
        result = _build_synthesize_workflow().run(hypothesis=hypothesis, blueprint=blueprint)
        _write_output(result.model_dump(mode="json"), args.out)
        return 0

    if args.command == "simulate":
        settings = load_runtime_settings(settings_dir=args.settings_dir)
        agenda, hypothesis, blueprint = _load_simulate_inputs(
            agenda_input_path=args.agenda_in,
            plan_input_path=args.plan_in,
            hypothesis_input_path=args.hypothesis_in,
            blueprint_input_path=args.blueprint_in,
        )
        run_id = args.run_id or _build_run_id("simulate", hypothesis.family)
        state_ledger = LocalFileStateLedger(args.artifacts_dir)
        payload = _execute_local_research_run(
            run_id=run_id,
            run_kind=RunKind.SIMULATE,
            settings=settings,
            state_ledger=state_ledger,
            artifacts_dir=args.artifacts_dir,
            agenda=agenda,
            hypothesis=hypothesis,
            blueprint=blueprint,
            fake_terminal_status=args.fake_terminal_status,
            max_polls=args.max_polls,
        )
        _write_output(payload, args.out)
        return 0

    if args.command == "research-loop":
        if args.iterations < 1:
            parser.exit(status=2, message="--iterations must be at least 1\n")

        settings = load_runtime_settings(settings_dir=args.settings_dir)
        seed_agendas = _load_seed_agendas(args.agenda_in)
        state_ledger = LocalFileStateLedger(args.artifacts_dir)
        selected_agenda_ids: list[str] = []
        selected_agenda_id_set: set[str] = set()
        iteration_runs: list[dict] = []
        stopped_reason = "completed_requested_iterations"

        for iteration_index in range(1, args.iterations + 1):
            _, learner_summaries = _resolve_family_analytics(args.artifacts_dir, state_ledger)
            family_recommendations = _build_family_policy_recommendations(learner_summaries)
            selection = _build_agenda_selection(
                seed_agendas,
                family_recommendations,
                excluded_agenda_ids=selected_agenda_id_set,
            )
            selected_agenda = selection.selected_agenda
            if selected_agenda is None:
                stopped_reason = "agenda_pool_exhausted"
                break

            run_id = _build_run_id("research_loop", selected_agenda.family)
            queue_recorded_at = _utc_now()
            state_ledger.append_agenda_queue_records(
                _build_agenda_queue_records(
                    run_id=run_id,
                    iteration_index=iteration_index,
                    agendas=seed_agendas,
                    agenda_recommendations=selection.agenda_recommendations,
                    selected_agenda_id=selected_agenda.agenda_id,
                    recorded_at=queue_recorded_at,
                )
            )

            plan_result = _build_plan_workflow().run(selected_agenda)
            run_payload = _execute_local_research_run(
                run_id=run_id,
                run_kind=RunKind.RESEARCH_LOOP,
                settings=settings,
                state_ledger=state_ledger,
                artifacts_dir=args.artifacts_dir,
                agenda=plan_result.agenda,
                hypothesis=plan_result.hypothesis,
                blueprint=plan_result.blueprint,
                fake_terminal_status=args.fake_terminal_status,
                max_polls=args.max_polls,
            )
            selected_agenda_ids.append(selected_agenda.agenda_id)
            selected_agenda_id_set.add(selected_agenda.agenda_id)
            iteration_runs.append(
                {
                    "iteration_index": iteration_index,
                    "run_id": run_payload["run_id"],
                    "selected_agenda_id": selected_agenda.agenda_id,
                    "selected_family": selected_agenda.family,
                    "accepted_candidate_ids": run_payload["accepted_candidate_ids"],
                    "promoted_candidate_ids": run_payload["promoted_candidate_ids"],
                    "simulation_status_counts": run_payload["simulation_status_counts"],
                    "top_agenda_ids": [
                        recommendation.agenda_id
                        for recommendation in selection.agenda_recommendations[:3]
                    ],
                    "top_family_recommendations": [
                        recommendation.family
                        for recommendation in family_recommendations[:3]
                    ],
                }
            )

        payload = {
            "requested_iterations": args.iterations,
            "completed_iterations": len(iteration_runs),
            "stopped_reason": stopped_reason,
            "seed_agenda_ids": [agenda.agenda_id for agenda in seed_agendas],
            "executed_agenda_ids": selected_agenda_ids,
            "state_dir": str(state_ledger.state_directory()),
            "iteration_runs": iteration_runs,
        }
        _write_output(payload, args.out)
        return 0

    if args.command == "validate":
        state_ledger = LocalFileStateLedger(args.artifacts_dir)
        try:
            source_candidate_run_id = _resolve_validate_source_run_id(
                state_ledger,
                args.source_run_id,
            )
            agenda, hypothesis, blueprint, candidates = _load_validate_inputs(
                args.artifacts_dir,
                state_ledger,
                source_candidate_run_id,
                args.candidate_id,
            )
        except ValueError as exc:
            parser.exit(status=2, message=f"{exc}\n")

        validation_stage = ValidationStage(args.validation_stage)
        run_id = _build_run_id("validate", hypothesis.family)
        started_at = _utc_now()
        state_ledger.append_validation_backlog_entries(
            _build_validation_backlog_entries(
                run_id=run_id,
                candidates=candidates,
                family=hypothesis.family,
                validation_stage=validation_stage,
                period=args.period,
                created_at=started_at,
                status=ValidationBacklogStatus.PENDING,
            )
        )
        state_ledger.append_run_state_records(
            [
                RunStateRecord(
                    run_id=run_id,
                    run_kind=RunKind.VALIDATE,
                    status=RunLifecycleStatus.STARTED,
                    started_at=started_at,
                )
            ]
        )

        try:
            result = _build_validate_workflow(base_time=started_at).run(
                source_run_id=run_id,
                candidate_source_run_id=source_candidate_run_id,
                hypothesis=hypothesis,
                blueprint=blueprint,
                candidates=candidates,
                validation_stage=validation_stage,
                period=args.period,
            )
            artifact_ledger = LocalFileArtifactLedger(args.artifacts_dir)
            artifact_run_dir = artifact_ledger.write_validation_result(
                run_id,
                result,
                agenda=agenda,
            )
            completed_at = _utc_now()
            state_ledger.append_validation_backlog_entries(
                _build_validation_backlog_entries(
                    run_id=run_id,
                    candidates=candidates,
                    family=hypothesis.family,
                    validation_stage=validation_stage,
                    period=args.period,
                    created_at=started_at,
                    status=ValidationBacklogStatus.COMPLETED,
                    updated_at=completed_at,
                )
            )
            state_ledger.append_run_state_records(
                [
                    RunStateRecord(
                        run_id=run_id,
                        run_kind=RunKind.VALIDATE,
                        status=RunLifecycleStatus.COMPLETED,
                        started_at=started_at,
                        completed_at=completed_at,
                        candidate_count=len(result.validated_candidate_ids),
                    )
                ]
            )

            payload = {
                "run_id": run_id,
                "source_candidate_run_id": source_candidate_run_id,
                "validation_stage": validation_stage.value,
                "period": args.period,
                "validated_candidate_ids": result.validated_candidate_ids,
                "passed_candidate_ids": result.passed_candidate_ids,
                "failed_candidate_ids": result.failed_candidate_ids,
                "artifact_run_dir": str(artifact_run_dir),
                "state_dir": str(state_ledger.state_directory()),
                "validation_summary": _build_validation_summary(
                    [outcome.validation for outcome in result.outcomes]
                ),
            }
            _write_output(payload, args.out)
            return 0
        except Exception as exc:
            state_ledger.append_validation_backlog_entries(
                _build_validation_backlog_entries(
                    run_id=run_id,
                    candidates=candidates,
                    family=hypothesis.family,
                    validation_stage=validation_stage,
                    period=args.period,
                    created_at=started_at,
                    status=ValidationBacklogStatus.CANCELLED,
                    updated_at=_utc_now(),
                )
            )
            state_ledger.append_run_state_records(
                [
                    RunStateRecord(
                        run_id=run_id,
                        run_kind=RunKind.VALIDATE,
                        status=RunLifecycleStatus.FAILED,
                        started_at=started_at,
                        completed_at=_utc_now(),
                        error_message=str(exc)[:300],
                    )
                ]
            )
            raise

    if args.command == "status":
        _write_output(_build_status_summary(args.artifacts_dir), args.out)
        return 0

    if args.command == "policy":
        state_ledger = LocalFileStateLedger(args.artifacts_dir)
        learner_summaries = state_ledger.load_family_learner_summaries()
        if not learner_summaries:
            analytics_bundle = _build_family_analytics_bundle(
                args.artifacts_dir,
                state_ledger.load_candidate_stage_records(),
            )
            learner_summaries = analytics_bundle.learner_summaries
        family_recommendations = _build_family_policy_recommendations(learner_summaries)
        agenda_recommendations = _build_agenda_priority_recommendations(
            _load_agendas(args.agenda_in),
            family_recommendations,
        )
        payload = {
            "family_recommendations": [
                recommendation.model_dump(mode="json")
                for recommendation in family_recommendations
            ],
            "agenda_recommendations": [
                recommendation.model_dump(mode="json")
                for recommendation in agenda_recommendations
            ],
        }
        _write_output(payload, args.out)
        return 0

    if args.command == "config":
        try:
            settings = load_runtime_settings(
                settings_dir=args.settings_dir,
                require_llm=args.require_llm,
                require_brain=args.require_brain,
            )
        except ValueError as exc:
            parser.exit(status=2, message=f"{exc}\n")
        payload = settings.model_dump(mode="json")
        _write_output(payload, args.out)
        return 0

    if args.command == "catalog":
        catalog = load_seed_metadata_catalog()
        if args.view == "summary":
            payload = {
                "field_count": len(catalog.fields),
                "operator_count": len(catalog.operators),
                "field_ids": [field.field_id for field in catalog.fields],
                "operator_ids": [operator.operator_id for operator in catalog.operators],
            }
        elif args.view == "fields":
            field_classes = [args.field_class] if args.field_class else None
            horizons = [args.horizon] if args.horizon else None
            payload = [
                entry.model_dump(mode="json")
                for entry in catalog.build_field_excerpt(
                    field_classes=field_classes,
                    horizons=horizons,
                    limit=args.limit,
                )
            ]
        else:
            payload = [
                operator.model_dump(mode="json")
                for operator in catalog.operators[: args.limit]
            ]
        _write_output(payload, args.out)
        return 0

    if args.command == "prompt":
        if args.sample_id:
            payload = load_prompt_golden_sample(args.role, args.sample_id).model_dump(mode="json")
        else:
            payload = load_prompt_asset(args.role).model_dump(mode="json")
        _write_output(payload, args.out)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 1
