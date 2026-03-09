from __future__ import annotations

import json
from pathlib import Path
from statistics import median

from pydantic import Field

from strategic_alpha_engine.application.contracts import EvaluationArtifactRecord, FamilyLearnerSummary, FamilyStatsSnapshot
from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.enums import CandidateLifecycleStage, EvaluationStage, SimulationStatus
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.application.contracts.state import CandidateStageRecord


class FamilyAnalyticsBundle(EngineModel):
    family_stats: list[FamilyStatsSnapshot] = Field(default_factory=list)
    learner_summaries: list[FamilyLearnerSummary] = Field(default_factory=list)


class LocalArtifactFamilyAnalyticsBuilder:
    def build(
        self,
        root_dir: str | Path,
        *,
        candidate_stage_records: list[CandidateStageRecord],
    ) -> FamilyAnalyticsBundle:
        artifacts_root = Path(root_dir).expanduser().resolve()
        latest_candidate_records = self._latest_candidate_stage_records(candidate_stage_records)
        records_by_family: dict[str, list[CandidateStageRecord]] = {}
        for record in latest_candidate_records.values():
            records_by_family.setdefault(record.family, []).append(record)

        family_by_run_id = self._load_family_by_run_id(artifacts_root)
        evaluation_records_by_family = self._load_stage_a_evaluations_by_family(
            artifacts_root,
            latest_candidate_records,
            family_by_run_id,
        )

        family_keys = sorted(set(records_by_family) | set(evaluation_records_by_family))
        family_stats: list[FamilyStatsSnapshot] = []
        learner_summaries: list[FamilyLearnerSummary] = []

        critique_passed_stages = {
            CandidateLifecycleStage.CRITIQUE_PASSED,
            CandidateLifecycleStage.SIM_PASSED,
            CandidateLifecycleStage.ROBUST_CANDIDATE,
            CandidateLifecycleStage.SUBMISSION_READY,
        }
        sim_passed_stages = {
            CandidateLifecycleStage.SIM_PASSED,
            CandidateLifecycleStage.ROBUST_CANDIDATE,
            CandidateLifecycleStage.SUBMISSION_READY,
        }
        robust_stages = {
            CandidateLifecycleStage.ROBUST_CANDIDATE,
            CandidateLifecycleStage.SUBMISSION_READY,
        }

        for family_key in family_keys:
            family_records = records_by_family.get(family_key, [])
            evaluations = evaluation_records_by_family.get(family_key, [])

            total_candidates = len(family_records)
            critique_passed_candidates = sum(
                1 for record in family_records if record.stage in critique_passed_stages
            )
            sim_passed_candidates = sum(
                1 for record in family_records if record.stage in sim_passed_stages
            )
            robust_candidates = sum(1 for record in family_records if record.stage in robust_stages)
            submission_ready_candidates = sum(
                1 for record in family_records if record.stage == CandidateLifecycleStage.SUBMISSION_READY
            )
            rejected_candidates = sum(
                1 for record in family_records if record.stage == CandidateLifecycleStage.REJECTED
            )

            simulation_candidate_count = len(evaluations)
            simulation_success_count = sum(
                1 for evaluation in evaluations if evaluation.evaluation.status == SimulationStatus.SUCCEEDED
            )
            simulation_failed_count = sum(
                1 for evaluation in evaluations if evaluation.evaluation.status == SimulationStatus.FAILED
            )
            simulation_timed_out_count = sum(
                1 for evaluation in evaluations if evaluation.evaluation.status == SimulationStatus.TIMED_OUT
            )
            stage_a_evaluation_count = simulation_candidate_count
            stage_a_passed_count = sum(
                1 for evaluation in evaluations if evaluation.evaluation.pass_decision
            )
            successful_sharpes = [
                evaluation.evaluation.sharpe
                for evaluation in evaluations
                if evaluation.evaluation.sharpe is not None
            ]
            median_stage_a_sharpe = round(median(successful_sharpes), 4) if successful_sharpes else None

            updated_candidates = [record.recorded_at for record in family_records]
            updated_evaluations = [evaluation.evaluation.evaluated_at for evaluation in evaluations]
            updated_at = max(updated_candidates + updated_evaluations)
            latest_run_id = self._resolve_latest_run_id(family_records, evaluations)

            critique_pass_rate = self._safe_rate(critique_passed_candidates, total_candidates)
            stage_a_pass_rate = self._safe_rate(stage_a_passed_count, stage_a_evaluation_count)
            simulation_timeout_rate = self._safe_rate(
                simulation_timed_out_count,
                simulation_candidate_count,
            )
            submission_ready_rate = self._safe_rate(submission_ready_candidates, total_candidates)

            family_stats.append(
                FamilyStatsSnapshot(
                    family=family_key,
                    total_candidates=total_candidates,
                    critique_passed_candidates=critique_passed_candidates,
                    sim_passed_candidates=sim_passed_candidates,
                    robust_candidates=robust_candidates,
                    submission_ready_candidates=submission_ready_candidates,
                    rejected_candidates=rejected_candidates,
                    simulation_candidate_count=simulation_candidate_count,
                    simulation_success_count=simulation_success_count,
                    simulation_failed_count=simulation_failed_count,
                    simulation_timed_out_count=simulation_timed_out_count,
                    stage_a_evaluation_count=stage_a_evaluation_count,
                    stage_a_passed_count=stage_a_passed_count,
                    median_stage_a_sharpe=median_stage_a_sharpe,
                    critique_pass_rate=critique_pass_rate,
                    stage_a_pass_rate=stage_a_pass_rate,
                    simulation_timeout_rate=simulation_timeout_rate,
                    submission_ready_rate=submission_ready_rate,
                    updated_at=updated_at,
                    last_run_id=latest_run_id,
                )
            )
            learner_summaries.append(
                FamilyLearnerSummary(
                    family=family_key,
                    total_candidates=total_candidates,
                    simulation_candidate_count=simulation_candidate_count,
                    critique_pass_rate=critique_pass_rate,
                    stage_a_pass_rate=stage_a_pass_rate,
                    simulation_timeout_rate=simulation_timeout_rate,
                    submission_ready_rate=submission_ready_rate,
                    median_stage_a_sharpe=median_stage_a_sharpe,
                    latest_run_id=latest_run_id,
                    updated_at=updated_at,
                )
            )

        return FamilyAnalyticsBundle(
            family_stats=family_stats,
            learner_summaries=learner_summaries,
        )

    def _latest_candidate_stage_records(
        self,
        candidate_stage_records: list[CandidateStageRecord],
    ) -> dict[str, CandidateStageRecord]:
        latest: dict[str, CandidateStageRecord] = {}
        for record in candidate_stage_records:
            latest[record.candidate_id] = record
        return latest

    def _load_family_by_run_id(self, artifacts_root: Path) -> dict[str, str]:
        family_by_run_id: dict[str, str] = {}
        for run_dir in sorted((artifacts_root / "runs").glob("*")):
            hypothesis_path = run_dir / "hypothesis.json"
            if not hypothesis_path.exists():
                continue
            payload = HypothesisSpec(**json.loads(hypothesis_path.read_text(encoding="utf-8")))
            family_by_run_id[run_dir.name] = payload.family
        return family_by_run_id

    def _load_stage_a_evaluations_by_family(
        self,
        artifacts_root: Path,
        latest_candidate_records: dict[str, CandidateStageRecord],
        family_by_run_id: dict[str, str],
    ) -> dict[str, list[EvaluationArtifactRecord]]:
        evaluations_by_family: dict[str, list[EvaluationArtifactRecord]] = {}
        runs_root = artifacts_root / "runs"
        if not runs_root.exists():
            return evaluations_by_family

        for evaluation_path in sorted(runs_root.glob("*/evaluations.jsonl")):
            for line in self._read_jsonl(evaluation_path):
                artifact = EvaluationArtifactRecord(**line)
                if artifact.evaluation.evaluation_stage != EvaluationStage.STAGE_A:
                    continue
                family = self._resolve_family_for_evaluation(
                    artifact,
                    latest_candidate_records,
                    family_by_run_id,
                )
                if family is None:
                    continue
                evaluations_by_family.setdefault(family, []).append(artifact)
        return evaluations_by_family

    def _resolve_family_for_evaluation(
        self,
        artifact: EvaluationArtifactRecord,
        latest_candidate_records: dict[str, CandidateStageRecord],
        family_by_run_id: dict[str, str],
    ) -> str | None:
        candidate_record = latest_candidate_records.get(artifact.evaluation.candidate_id)
        if candidate_record is not None:
            return candidate_record.family
        return family_by_run_id.get(artifact.evaluation.source_run_id)

    def _resolve_latest_run_id(
        self,
        family_records: list[CandidateStageRecord],
        evaluations: list[EvaluationArtifactRecord],
    ) -> str | None:
        latest_record = None
        latest_recorded_at = None
        for record in family_records:
            if latest_recorded_at is None or record.recorded_at > latest_recorded_at:
                latest_record = record
                latest_recorded_at = record.recorded_at
        for evaluation in evaluations:
            if latest_recorded_at is None or evaluation.evaluation.evaluated_at > latest_recorded_at:
                latest_record = evaluation.evaluation
                latest_recorded_at = evaluation.evaluation.evaluated_at
        if latest_record is None:
            return None
        return latest_record.source_run_id if hasattr(latest_record, "source_run_id") else None

    def _safe_rate(self, numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(numerator / denominator, 4)

    def _read_jsonl(self, path: Path) -> list[dict]:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return []
        return [json.loads(line) for line in content.splitlines()]
