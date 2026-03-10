from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from strategic_alpha_engine.application.contracts import (
    AgendaQueueRecord,
    AutopilotManifest,
    CandidateStageRecord,
    FamilyLearnerSummary,
    FamilyStatsSnapshot,
    HumanReviewQueueRecord,
    RunStateRecord,
    SubmissionPacketIndexRecord,
    SubmissionReadyCandidateRecord,
    ValidationPromotionArtifactRecord,
    ValidationBacklogEntry,
)
from strategic_alpha_engine.application.services import (
    FamilyAnalyticsBundle,
    HeuristicSearchPolicyLearner,
    LocalArtifactFamilyAnalyticsBuilder,
    MetadataBackedStaticValidator,
)
from strategic_alpha_engine.application.workflows import (
    AutopilotWorkflow,
    build_validation_matrix,
)
from strategic_alpha_engine.config import RuntimeSettings, load_runtime_settings
from strategic_alpha_engine.domain import (
    CritiqueReport,
    ExpressionCandidate,
    HypothesisSpec,
    ResearchAgenda,
    SignalBlueprint,
    StaticValidationReport,
    ValidationRecord,
    build_sample_critique_report,
    build_sample_expression_candidate,
    build_sample_hypothesis_spec,
    build_sample_research_agenda,
    build_sample_signal_blueprint,
    build_sample_validation_record,
)
from strategic_alpha_engine.domain.enums import (
    AutopilotStopReason,
    CandidateLifecycleStage,
    FieldClass,
    HumanReviewDecisionKind,
    HumanReviewQueueStatus,
    ResearchHorizon,
    RunKind,
    RunLifecycleStatus,
    SimulationStatus,
    ValidationBacklogStatus,
)
from strategic_alpha_engine.domain.review import HumanReviewDecision
from strategic_alpha_engine.infrastructure.artifacts import LocalFileArtifactLedger
from strategic_alpha_engine.infrastructure.metadata import load_seed_metadata_catalog
from strategic_alpha_engine.infrastructure.state import LocalFileStateLedger
from strategic_alpha_engine.interfaces.cli.autopilot_runtime import (
    build_autopilot_workflow,
    load_agenda_catalog,
)
from strategic_alpha_engine.prompts import PromptRole, load_prompt_asset, load_prompt_golden_sample


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


def _build_config_payload(settings: RuntimeSettings) -> dict:
    payload = settings.model_dump(mode="json")
    if settings.brain is not None:
        payload["brain"] = {
            "base_url": settings.brain.base_url,
            "username": settings.brain.username,
            "password_configured": bool(settings.brain.password),
            "submit_timeout_seconds": settings.brain.submit_timeout_seconds,
            "poll_interval_seconds": settings.brain.poll_interval_seconds,
            "max_polls": settings.brain.max_polls,
        }
    return payload


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


def _build_stage_counts(candidate_stage_records: list[CandidateStageRecord]) -> dict[str, int]:
    counts = {stage.value: 0 for stage in CandidateLifecycleStage}
    for record in _latest_candidate_stage_records(candidate_stage_records).values():
        counts[record.stage] += 1
    return counts


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


def _load_robust_promotion_records(
    root_dir: str | Path,
    run_state_records: list[RunStateRecord],
) -> list[ValidationPromotionArtifactRecord]:
    artifacts_root = Path(root_dir).expanduser().resolve()
    promotion_records: list[ValidationPromotionArtifactRecord] = []
    candidate_fields = set(ExpressionCandidate.model_fields)
    for record in _latest_run_state_records(run_state_records).values():
        if record.run_kind != RunKind.VALIDATE:
            continue
        promotions_path = artifacts_root / "runs" / record.run_id / "robust_promotion.jsonl"
        for payload in _read_jsonl_file(promotions_path):
            candidate_payload = payload.get("candidate", {})
            promotion_records.append(
                ValidationPromotionArtifactRecord(
                    **{
                        **payload,
                        "candidate": {
                            key: value
                            for key, value in candidate_payload.items()
                            if key in candidate_fields
                        },
                    }
                )
            )
    return promotion_records


def _build_pending_human_review_queue_records(
    records: list[SubmissionReadyCandidateRecord],
) -> list[HumanReviewQueueRecord]:
    queue_records: list[HumanReviewQueueRecord] = []
    for record in records:
        queue_entry_id = f"review_queue.{record.source_run_id}.{record.candidate_id}"
        queue_records.append(
            HumanReviewQueueRecord(
                queue_record_id=f"{queue_entry_id}.pending",
                queue_entry_id=queue_entry_id,
                inventory_record_id=record.inventory_record_id,
                candidate_id=record.candidate_id,
                hypothesis_id=record.hypothesis_id,
                blueprint_id=record.blueprint_id,
                family=record.family,
                submission_ready_source_run_id=record.source_run_id,
                status=HumanReviewQueueStatus.PENDING,
                source_run_id=record.source_run_id,
                priority=0.85,
                created_at=record.promoted_at,
                notes="queued for human review after submission_ready promotion",
            )
        )
    return queue_records


def _load_submission_packet_payloads(
    root_dir: str | Path,
    run_state_records: list[RunStateRecord],
) -> list[dict]:
    artifacts_root = Path(root_dir).expanduser().resolve()
    payloads: list[dict] = []
    for record in _latest_run_state_records(run_state_records).values():
        if record.run_kind != RunKind.PACKET:
            continue
        payloads.extend(
            _read_jsonl_file(
                artifacts_root / "runs" / record.run_id / "submission_packets.jsonl"
            )
        )
    return payloads


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


def _build_validation_matrix_summary(validation_records: list[ValidationRecord]) -> dict:
    if not validation_records:
        return {
            "latest_run_id": None,
            "validation_stage": None,
            "requested_periods": [],
            "required_passing_periods": None,
            "total_candidates": 0,
            "passed_candidate_count": 0,
            "failed_candidate_count": 0,
            "rows": [],
        }

    latest_record = max(validation_records, key=lambda record: record.validated_at)
    latest_run_id = latest_record.source_run_id
    latest_run_records = [
        record
        for record in validation_records
        if record.source_run_id == latest_run_id
    ]
    latest_run_records.sort(key=lambda record: (record.candidate_id, record.period))
    validation_stage = latest_run_records[0].validation_stage
    requested_periods: list[str] = []
    for record in latest_run_records:
        if record.period not in requested_periods:
            requested_periods.append(record.period)

    matrix = build_validation_matrix(
        latest_run_records,
        source_run_id=latest_run_id,
        validation_stage=validation_stage,
        requested_periods=requested_periods,
    )
    return matrix.model_dump(mode="json")


def _build_robust_promotion_summary(
    promotion_records: list[ValidationPromotionArtifactRecord],
) -> dict:
    if not promotion_records:
        return {
            "latest_run_id": None,
            "total_decisions": 0,
            "counts_by_decision": {},
            "counts_by_target_stage": {},
            "promoted_candidate_ids": [],
            "held_candidate_ids": [],
            "rejected_candidate_ids": [],
        }

    latest_record = max(
        promotion_records,
        key=lambda record: record.promotion.decided_at,
    )
    latest_run_id = latest_record.promotion.source_run_id
    latest_run_records = [
        record
        for record in promotion_records
        if record.promotion.source_run_id == latest_run_id
    ]
    decision_counts: Counter[str] = Counter(
        record.promotion.decision
        for record in latest_run_records
    )
    target_stage_counts: Counter[str] = Counter(
        record.promotion.to_stage
        for record in latest_run_records
    )

    return {
        "latest_run_id": latest_run_id,
        "total_decisions": len(latest_run_records),
        "counts_by_decision": dict(sorted(decision_counts.items())),
        "counts_by_target_stage": dict(sorted(target_stage_counts.items())),
        "promoted_candidate_ids": [
            record.candidate.candidate_id
            for record in latest_run_records
            if record.promotion.to_stage == CandidateLifecycleStage.ROBUST_CANDIDATE
        ],
        "held_candidate_ids": [
            record.candidate.candidate_id
            for record in latest_run_records
            if record.promotion.to_stage == CandidateLifecycleStage.SIM_PASSED
        ],
        "rejected_candidate_ids": [
            record.candidate.candidate_id
            for record in latest_run_records
            if record.promotion.to_stage == CandidateLifecycleStage.REJECTED
        ],
    }


def _latest_human_review_queue_records(
    records: list[HumanReviewQueueRecord],
) -> list[HumanReviewQueueRecord]:
    latest: dict[str, HumanReviewQueueRecord] = {}
    for record in records:
        current = latest.get(record.queue_entry_id)
        current_timestamp = (current.updated_at or current.created_at) if current is not None else None
        record_timestamp = record.updated_at or record.created_at
        if current_timestamp is None or record_timestamp >= current_timestamp:
            latest[record.queue_entry_id] = record
    return list(latest.values())


def _build_human_review_queue_summary(
    queue_records: list[HumanReviewQueueRecord],
) -> dict:
    latest_records = _latest_human_review_queue_records(queue_records)
    if not latest_records:
        return {
            "latest_run_id": None,
            "total_entries": 0,
            "counts_by_status": {},
            "pending_candidate_ids": [],
            "entries": [],
        }

    latest_records.sort(
        key=lambda record: (record.updated_at or record.created_at, record.candidate_id),
        reverse=True,
    )
    counts_by_status: Counter[str] = Counter(record.status for record in latest_records)
    latest_record = latest_records[0]
    return {
        "latest_run_id": latest_record.source_run_id,
        "total_entries": len(latest_records),
        "counts_by_status": dict(sorted(counts_by_status.items())),
        "pending_candidate_ids": [
            record.candidate_id
            for record in latest_records
            if record.status == HumanReviewQueueStatus.PENDING
        ],
        "entries": [record.model_dump(mode="json") for record in latest_records[:10]],
    }


def _build_human_review_summary(
    review_decisions: list[HumanReviewDecision],
) -> dict:
    if not review_decisions:
        return {
            "latest_run_id": None,
            "total_decisions": 0,
            "counts_by_decision": {},
            "counts_by_to_stage": {},
            "approved_candidate_ids": [],
            "held_candidate_ids": [],
            "rejected_candidate_ids": [],
        }

    latest_record = max(review_decisions, key=lambda record: record.reviewed_at)
    latest_run_id = latest_record.source_run_id
    latest_run_records = [
        record
        for record in review_decisions
        if record.source_run_id == latest_run_id
    ]
    decision_counts: Counter[str] = Counter(record.decision for record in latest_run_records)
    target_stage_counts: Counter[str] = Counter(record.to_stage for record in latest_run_records)
    return {
        "latest_run_id": latest_run_id,
        "total_decisions": len(latest_run_records),
        "counts_by_decision": dict(sorted(decision_counts.items())),
        "counts_by_to_stage": dict(sorted(target_stage_counts.items())),
        "approved_candidate_ids": [
            record.candidate_id
            for record in latest_run_records
            if record.decision == HumanReviewDecisionKind.APPROVE
        ],
        "held_candidate_ids": [
            record.candidate_id
            for record in latest_run_records
            if record.decision == HumanReviewDecisionKind.HOLD
        ],
        "rejected_candidate_ids": [
            record.candidate_id
            for record in latest_run_records
            if record.decision == HumanReviewDecisionKind.REJECT
        ],
    }


def _build_submission_packet_summary(packet_payloads: list[dict]) -> dict:
    if not packet_payloads:
        return {
            "latest_run_id": None,
            "latest_generated_at": None,
            "review_source_run_id": None,
            "submission_ready_source_run_ids": [],
            "total_packets": 0,
            "counts_by_family": {},
            "candidate_ids": [],
            "packet_ids": [],
            "entries": [],
        }

    latest_payload = max(
        packet_payloads,
        key=lambda payload: payload.get("generated_at", ""),
    )
    latest_run_id = latest_payload["source_run_id"]
    latest_run_payloads = [
        payload
        for payload in packet_payloads
        if payload.get("source_run_id") == latest_run_id
    ]
    latest_run_payloads.sort(
        key=lambda payload: payload["candidate_artifact"]["candidate"]["candidate_id"]
    )
    counts_by_family: Counter[str] = Counter(
        (payload.get("hypothesis") or {}).get("family")
        for payload in latest_run_payloads
        if (payload.get("hypothesis") or {}).get("family")
    )
    submission_ready_source_run_ids: list[str] = []
    for payload in latest_run_payloads:
        source_run_id = payload.get("submission_ready_source_run_id")
        if source_run_id and source_run_id not in submission_ready_source_run_ids:
            submission_ready_source_run_ids.append(source_run_id)

    return {
        "latest_run_id": latest_run_id,
        "latest_generated_at": latest_payload.get("generated_at"),
        "review_source_run_id": latest_payload.get("review_source_run_id"),
        "submission_ready_source_run_ids": submission_ready_source_run_ids,
        "total_packets": len(latest_run_payloads),
        "counts_by_family": dict(sorted(counts_by_family.items())),
        "candidate_ids": [
            payload["candidate_artifact"]["candidate"]["candidate_id"]
            for payload in latest_run_payloads
        ],
        "packet_ids": [payload["packet_id"] for payload in latest_run_payloads],
        "entries": [
            {
                "packet_id": payload["packet_id"],
                "candidate_id": payload["candidate_artifact"]["candidate"]["candidate_id"],
                "family": (payload.get("hypothesis") or {}).get("family"),
                "review_source_run_id": payload.get("review_source_run_id"),
                "submission_ready_source_run_id": payload.get("submission_ready_source_run_id"),
                "generated_at": payload.get("generated_at"),
            }
            for payload in latest_run_payloads[:10]
        ],
    }


def _submission_packet_index_rank_key(record: SubmissionPacketIndexRecord) -> tuple:
    return (
        -record.passing_period_count,
        -(record.stage_a_sharpe if record.stage_a_sharpe is not None else float("-inf")),
        -(record.fitness if record.fitness is not None else float("-inf")),
        abs((record.turnover if record.turnover is not None else 0.25) - 0.25)
        if record.turnover is not None
        else float("inf"),
        record.candidate_id,
    )


def _build_submission_packet_index_summary(
    records: list[SubmissionPacketIndexRecord],
) -> dict:
    if not records:
        return {
            "total_records": 0,
            "unique_signatures": 0,
            "latest_autopilot_run_id": None,
            "candidate_ids": [],
            "packet_ids": [],
            "entries": [],
        }

    best_by_signature: dict[str, SubmissionPacketIndexRecord] = {}
    for record in records:
        current = best_by_signature.get(record.signature)
        if current is None or _submission_packet_index_rank_key(record) < _submission_packet_index_rank_key(current):
            best_by_signature[record.signature] = record

    latest_record = max(records, key=lambda record: record.recorded_at)
    selected_records = sorted(best_by_signature.values(), key=_submission_packet_index_rank_key)
    return {
        "total_records": len(records),
        "unique_signatures": len(best_by_signature),
        "latest_autopilot_run_id": latest_record.autopilot_run_id,
        "candidate_ids": [record.candidate_id for record in selected_records],
        "packet_ids": [record.packet_id for record in selected_records],
        "entries": [
            record.model_dump(mode="json")
            for record in selected_records[:10]
        ],
    }


def _build_autopilot_status_summary(
    run_state_records: list[RunStateRecord],
    latest_manifest: AutopilotManifest | None,
    artifacts_root: Path,
) -> dict:
    latest_run_records = list(_latest_run_state_records(run_state_records).values())
    latest_run_records.sort(
        key=lambda record: record.completed_at or record.started_at,
        reverse=True,
    )
    autopilot_records = [
        record
        for record in latest_run_records
        if record.run_kind == RunKind.AUTOPILOT
    ]
    if not autopilot_records:
        return {
            "current_state": "not_started",
            "latest_run_id": None,
            "stop_reason": None,
            "ready_for_submission_packet_count": 0,
            "latest_submission_manifest_path": None,
        }

    latest_record = autopilot_records[0]
    if latest_record.status == RunLifecycleStatus.STARTED:
        current_state = "running"
    elif latest_record.status == RunLifecycleStatus.FAILED:
        current_state = "failed"
    else:
        current_state = "idle"

    manifest_path = artifacts_root / "state" / "latest_submission_manifest.json"
    return {
        "current_state": current_state,
        "latest_run_id": latest_record.run_id,
        "stop_reason": latest_manifest.stopped_reason if latest_manifest is not None else None,
        "ready_for_submission_packet_count": (
            latest_manifest.selected_packet_count
            if latest_manifest is not None
            else 0
        ),
        "latest_submission_manifest_path": str(manifest_path) if manifest_path.exists() else None,
    }


def _latest_submission_ready_records(
    records: list[SubmissionReadyCandidateRecord],
) -> list[SubmissionReadyCandidateRecord]:
    latest: dict[str, SubmissionReadyCandidateRecord] = {}
    for record in records:
        current = latest.get(record.candidate_id)
        if current is None or record.promoted_at >= current.promoted_at:
            latest[record.candidate_id] = record
    return list(latest.values())


def _build_submission_ready_inventory_summary(
    records: list[SubmissionReadyCandidateRecord],
    candidate_stage_records: list[CandidateStageRecord] | None = None,
) -> dict:
    latest_records = _latest_submission_ready_records(records)
    if candidate_stage_records is not None:
        latest_stage_records = _latest_candidate_stage_records(candidate_stage_records)
        latest_records = [
            record
            for record in latest_records
            if latest_stage_records.get(record.candidate_id) is not None
            and latest_stage_records[record.candidate_id].stage == CandidateLifecycleStage.SUBMISSION_READY
        ]
    if not latest_records:
        return {
            "latest_run_id": None,
            "latest_promoted_at": None,
            "total_candidates": 0,
            "counts_by_family": {},
            "candidate_ids": [],
            "entries": [],
        }

    latest_records.sort(key=lambda record: (record.promoted_at, record.candidate_id), reverse=True)
    counts_by_family: Counter[str] = Counter(record.family for record in latest_records)
    latest_record = latest_records[0]
    return {
        "latest_run_id": latest_record.source_run_id,
        "latest_promoted_at": latest_record.promoted_at.isoformat(),
        "total_candidates": len(latest_records),
        "counts_by_family": dict(sorted(counts_by_family.items())),
        "candidate_ids": [record.candidate_id for record in latest_records],
        "entries": [record.model_dump(mode="json") for record in latest_records[:10]],
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


def _build_robust_candidate_stage_records(
    *,
    run_id: str,
    hypothesis: HypothesisSpec,
    blueprint: SignalBlueprint,
    promotion_result,
) -> list[CandidateStageRecord]:
    records: list[CandidateStageRecord] = []
    for outcome in promotion_result.outcomes:
        note = f"robust promotion decision: {outcome.promotion.decision}"
        if outcome.promotion.reasons:
            note = f"{note}; {'; '.join(outcome.promotion.reasons[:2])}"
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
                notes=note[:240],
            )
        )
    return records


def _build_submission_ready_stage_records(
    *,
    run_id: str,
    hypothesis: HypothesisSpec,
    blueprint: SignalBlueprint,
    promotion_result,
) -> list[CandidateStageRecord]:
    records: list[CandidateStageRecord] = []
    for outcome in promotion_result.outcomes:
        note = "submission-ready promotion: promote"
        if outcome.submission_promotion.reasons:
            note = f"{note}; {'; '.join(outcome.submission_promotion.reasons[:2])}"
        records.append(
            CandidateStageRecord(
                stage_record_id=(
                    f"stage.{run_id}.{outcome.robust_promotion.candidate.candidate_id}."
                    f"{outcome.submission_promotion.to_stage}"
                ),
                candidate_id=outcome.robust_promotion.candidate.candidate_id,
                hypothesis_id=hypothesis.hypothesis_id,
                blueprint_id=blueprint.blueprint_id,
                family=hypothesis.family,
                stage=outcome.submission_promotion.to_stage,
                source_run_id=run_id,
                recorded_at=outcome.submission_promotion.decided_at,
                notes=note[:240],
            )
        )
    return records


def _build_submission_ready_inventory_records(
    *,
    run_id: str,
    hypothesis: HypothesisSpec,
    blueprint: SignalBlueprint,
    promotion_result,
) -> list[SubmissionReadyCandidateRecord]:
    records: list[SubmissionReadyCandidateRecord] = []
    for outcome in promotion_result.outcomes:
        robust_record = outcome.robust_promotion
        records.append(
            SubmissionReadyCandidateRecord(
                inventory_record_id=f"submission_ready.{run_id}.{robust_record.candidate.candidate_id}",
                candidate_id=robust_record.candidate.candidate_id,
                hypothesis_id=hypothesis.hypothesis_id,
                blueprint_id=blueprint.blueprint_id,
                family=hypothesis.family,
                source_run_id=run_id,
                robust_source_run_id=promotion_result.robust_source_run_id,
                promotion_id=outcome.submission_promotion.promotion_id,
                validation_ids=robust_record.validation_ids,
                requested_periods=robust_record.requested_periods,
                promoted_at=outcome.submission_promotion.decided_at,
                notes="manual promote CLI advanced candidate to submission_ready",
            )
        )
    return records


def _build_human_review_stage_records(
    *,
    run_id: str,
    hypothesis: HypothesisSpec,
    blueprint: SignalBlueprint,
    review_result,
) -> list[CandidateStageRecord]:
    records: list[CandidateStageRecord] = []
    for outcome in review_result.outcomes:
        note = f"human review decision: {outcome.review_decision.decision}"
        if outcome.review_decision.reasons:
            note = f"{note}; {'; '.join(outcome.review_decision.reasons[:2])}"
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
                notes=note[:240],
            )
        )
    return records


def _build_resolved_human_review_queue_records(
    *,
    run_id: str,
    pending_queue_records: list[HumanReviewQueueRecord],
    review_result,
) -> list[HumanReviewQueueRecord]:
    pending_by_candidate_id = {
        record.candidate_id: record
        for record in pending_queue_records
    }
    queue_status_map = {
        HumanReviewDecisionKind.APPROVE: HumanReviewQueueStatus.APPROVED,
        HumanReviewDecisionKind.HOLD: HumanReviewQueueStatus.HELD,
        HumanReviewDecisionKind.REJECT: HumanReviewQueueStatus.REJECTED,
    }
    records: list[HumanReviewQueueRecord] = []
    for outcome in review_result.outcomes:
        pending_record = pending_by_candidate_id[outcome.submission_ready.candidate.candidate_id]
        decision = HumanReviewDecisionKind(outcome.review_decision.decision)
        records.append(
            HumanReviewQueueRecord(
                queue_record_id=(
                    "review_queue_update."
                    f"{run_id}.{pending_record.candidate_id}.{decision.value}"
                ),
                queue_entry_id=pending_record.queue_entry_id,
                inventory_record_id=pending_record.inventory_record_id,
                candidate_id=pending_record.candidate_id,
                hypothesis_id=pending_record.hypothesis_id,
                blueprint_id=pending_record.blueprint_id,
                family=pending_record.family,
                submission_ready_source_run_id=pending_record.submission_ready_source_run_id,
                status=queue_status_map[decision],
                source_run_id=run_id,
                priority=pending_record.priority,
                reviewer=outcome.review_decision.reviewer,
                decision_id=outcome.review_decision.decision_id,
                created_at=pending_record.created_at,
                updated_at=outcome.review_decision.reviewed_at,
                notes=outcome.review_decision.notes,
            )
        )
    return records


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
    submission_ready_records = state_ledger.load_submission_ready_records()
    human_review_queue_records = state_ledger.load_human_review_queue_records()
    human_review_decisions = state_ledger.load_human_review_decisions()
    submission_packet_index_records = state_ledger.load_submission_packet_index_records()
    latest_submission_manifest = state_ledger.load_latest_submission_manifest()
    latest_validation_backlog_entries = _latest_validation_backlog_entries(validation_backlog_entries)
    validation_records = _load_validation_records(artifacts_root, run_state_records)
    robust_promotion_records = _load_robust_promotion_records(artifacts_root, run_state_records)
    submission_packet_payloads = _load_submission_packet_payloads(artifacts_root, run_state_records)

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
        "autopilot_status": _build_autopilot_status_summary(
            run_state_records,
            latest_submission_manifest,
            artifacts_root,
        ),
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
        "validation_matrix": _build_validation_matrix_summary(validation_records),
        "robust_promotion_summary": _build_robust_promotion_summary(robust_promotion_records),
        "submission_ready_inventory": _build_submission_ready_inventory_summary(
            submission_ready_records,
            candidate_stage_records=candidate_stage_records,
        ),
        "human_review_queue": _build_human_review_queue_summary(human_review_queue_records),
        "human_review_summary": _build_human_review_summary(human_review_decisions),
        "submission_packet_summary": _build_submission_packet_summary(submission_packet_payloads),
        "submission_packet_index": _build_submission_packet_index_summary(
            submission_packet_index_records
        ),
        "latest_submission_manifest": (
            latest_submission_manifest.model_dump(mode="json")
            if latest_submission_manifest is not None
            else None
        ),
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

    autopilot_parser = subparsers.add_parser(
        "autopilot",
        help="Run the full autopilot alpha factory and emit a submission manifest",
    )
    autopilot_parser.add_argument("--settings-dir", default=None)
    autopilot_parser.add_argument("--artifacts-dir", default="artifacts")
    autopilot_parser.add_argument("--agenda-catalog-in", default=None)
    autopilot_parser.add_argument("--run-id", default=None)
    autopilot_parser.add_argument(
        "--brain-provider",
        choices=["fake", "worldquant"],
        default="worldquant",
    )
    autopilot_parser.add_argument(
        "--fake-terminal-status",
        choices=[
            SimulationStatus.SUCCEEDED.value,
            SimulationStatus.FAILED.value,
            SimulationStatus.TIMED_OUT.value,
        ],
        default=SimulationStatus.SUCCEEDED.value,
    )
    autopilot_parser.add_argument("--target-packet-count", type=int, default=None)
    autopilot_parser.add_argument("--packet-top-k", type=int, default=None)
    autopilot_parser.add_argument("--max-agendas", type=int, default=None)
    autopilot_parser.add_argument("--max-simulations", type=int, default=None)
    autopilot_parser.add_argument("--idle-rounds", type=int, default=None)
    autopilot_parser.add_argument("--max-polls", type=int, default=None)
    autopilot_parser.add_argument("--out", default=None)

    status_parser = subparsers.add_parser("status", help="Summarize local artifact and state ledgers")
    status_parser.add_argument("--artifacts-dir", default="artifacts")
    status_parser.add_argument("--out", default=None)

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
    prompt_parser.add_argument(
        "--role",
        choices=[
            PromptRole.AGENDA_GENERATOR.value,
            PromptRole.PLANNER.value,
            PromptRole.BLUEPRINT.value,
            PromptRole.CRITIC.value,
        ],
        required=True,
    )
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

    if args.command == "autopilot":
        try:
            settings = load_runtime_settings(
                settings_dir=args.settings_dir,
                require_llm=True,
                require_brain=args.brain_provider == "worldquant",
            )
            autopilot_overrides = {
                key: value
                for key, value in {
                    "target_packet_count": args.target_packet_count,
                    "packet_top_k": args.packet_top_k,
                    "max_agendas": args.max_agendas,
                    "max_simulations": args.max_simulations,
                    "idle_rounds": args.idle_rounds,
                }.items()
                if value is not None
            }
            if autopilot_overrides:
                settings = settings.model_copy(
                    update={
                        "autopilot": settings.autopilot.model_copy(
                            update=autopilot_overrides,
                        )
                    }
                )
            seed_agendas = load_agenda_catalog(args.agenda_catalog_in)
        except ValueError as exc:
            parser.exit(status=2, message=f"{exc}\n")

        workflow = build_autopilot_workflow(
            settings=settings,
            artifacts_dir=args.artifacts_dir,
            brain_provider=args.brain_provider,
            fake_terminal_status=args.fake_terminal_status,
            max_polls=args.max_polls,
        )
        run_id = args.run_id or _build_run_id("autopilot", "factory")
        result = workflow.run(
            autopilot_run_id=run_id,
            artifacts_dir=args.artifacts_dir,
            seed_agendas=seed_agendas,
        )
        state_ledger = LocalFileStateLedger(args.artifacts_dir)
        payload = {
            "run_id": result.autopilot_run_id,
            "stopped_reason": result.stopped_reason,
            "agenda_catalog_count": result.agenda_catalog_count,
            "iteration_count": len(result.iteration_records),
            "selected_candidate_ids": result.selected_candidate_ids,
            "packet_ids": result.packet_ids,
            "packet_paths": result.packet_paths,
            "packet_index_added_count": result.packet_index_added_count,
            "latest_submission_manifest": result.manifest.model_dump(mode="json"),
            "state_dir": str(state_ledger.state_directory()),
        }
        _write_output(payload, args.out)
        return 0

    if args.command == "status":
        _write_output(_build_status_summary(args.artifacts_dir), args.out)
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
        payload = _build_config_payload(settings)
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
