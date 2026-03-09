from __future__ import annotations

import json
from pathlib import Path

from strategic_alpha_engine.application.contracts import (
    CandidateArtifactRecord,
    EvaluationArtifactRecord,
    HumanReviewArtifactRecord,
    PromotionArtifactRecord,
    SubmissionReadyArtifactRecord,
    SimulationArtifactRecord,
    ValidationArtifactRecord,
    ValidationPromotionArtifactRecord,
)
from strategic_alpha_engine.application.workflows.plan import PlanResult
from strategic_alpha_engine.application.workflows.evaluate_stage_a import StageACandidateOutcome, StageAEvaluationResult
from strategic_alpha_engine.application.workflows.promote_robust_candidates import (
    RobustPromotionOutcome,
    RobustPromotionResult,
)
from strategic_alpha_engine.application.workflows.promote_submission_ready import (
    SubmissionReadyPromotionOutcome,
    SubmissionReadyPromotionResult,
)
from strategic_alpha_engine.application.workflows.review_submission_ready import (
    HumanReviewOutcome,
    HumanReviewResult,
)
from strategic_alpha_engine.application.workflows.simulate import (
    SimulationCandidateExecution,
    SimulationOrchestratorResult,
)
from strategic_alpha_engine.application.workflows.synthesize import CandidateEvaluation, SynthesizeResult
from strategic_alpha_engine.application.workflows.validate import (
    MultiPeriodValidateResult,
    ValidateResult,
    ValidationOutcome,
)
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.application.contracts.state import HumanReviewQueueRecord
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec


class LocalFileArtifactLedger:
    def __init__(self, root_dir: str | Path = "artifacts"):
        self.root_dir = Path(root_dir).expanduser().resolve()

    def run_directory(self, run_id: str) -> Path:
        path = self.root_dir / "runs" / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_context(
        self,
        run_id: str,
        *,
        agenda: ResearchAgenda | None,
        hypothesis: HypothesisSpec,
        blueprint: SignalBlueprint,
    ) -> Path:
        run_dir = self.run_directory(run_id)
        if agenda is not None:
            self._write_json(run_dir / "agenda.json", agenda.model_dump(mode="json"))
        self._write_json(run_dir / "hypothesis.json", hypothesis.model_dump(mode="json"))
        self._write_json(run_dir / "blueprint.json", blueprint.model_dump(mode="json"))
        return run_dir

    def write_candidate_records(
        self,
        run_id: str,
        records: list[CandidateArtifactRecord],
    ) -> Path:
        run_dir = self.run_directory(run_id)
        self._write_jsonl(
            run_dir / "candidates.jsonl",
            [record.candidate.model_dump(mode="json") for record in records],
        )
        self._write_jsonl(
            run_dir / "validations.jsonl",
            [record.validation.model_dump(mode="json") for record in records],
        )
        self._write_jsonl(
            run_dir / "critiques.jsonl",
            [record.critique.model_dump(mode="json") for record in records if record.critique is not None],
        )
        return run_dir

    def write_simulation_records(
        self,
        run_id: str,
        records: list[SimulationArtifactRecord],
    ) -> Path:
        run_dir = self.run_directory(run_id)
        self._write_jsonl(
            run_dir / "simulations.jsonl",
            [record.model_dump(mode="json") for record in records],
        )
        return run_dir

    def write_evaluation_records(
        self,
        run_id: str,
        records: list[EvaluationArtifactRecord],
    ) -> Path:
        run_dir = self.run_directory(run_id)
        self._write_jsonl(
            run_dir / "evaluations.jsonl",
            [record.model_dump(mode="json") for record in records],
        )
        return run_dir

    def write_promotion_records(
        self,
        run_id: str,
        records: list[PromotionArtifactRecord],
    ) -> Path:
        run_dir = self.run_directory(run_id)
        self._write_jsonl(
            run_dir / "promotion.jsonl",
            [record.model_dump(mode="json") for record in records],
        )
        return run_dir

    def write_validation_records(
        self,
        run_id: str,
        records: list[ValidationArtifactRecord],
    ) -> Path:
        run_dir = self.run_directory(run_id)
        self._write_jsonl(
            run_dir / "validations.jsonl",
            [record.model_dump(mode="json") for record in records],
        )
        return run_dir

    def write_robust_promotion_records(
        self,
        run_id: str,
        records: list[ValidationPromotionArtifactRecord],
    ) -> Path:
        run_dir = self.run_directory(run_id)
        self._write_jsonl(
            run_dir / "robust_promotion.jsonl",
            [record.model_dump(mode="json") for record in records],
        )
        return run_dir

    def write_submission_ready_records(
        self,
        run_id: str,
        records: list[SubmissionReadyArtifactRecord],
    ) -> Path:
        run_dir = self.run_directory(run_id)
        self._write_jsonl(
            run_dir / "submission_ready.jsonl",
            [record.model_dump(mode="json") for record in records],
        )
        return run_dir

    def write_human_review_records(
        self,
        run_id: str,
        records: list[HumanReviewArtifactRecord],
    ) -> Path:
        run_dir = self.run_directory(run_id)
        self._write_jsonl(
            run_dir / "human_review.jsonl",
            [record.model_dump(mode="json") for record in records],
        )
        return run_dir

    def write_review_queue_records(
        self,
        run_id: str,
        records: list[HumanReviewQueueRecord],
    ) -> Path:
        run_dir = self.run_directory(run_id)
        self._write_jsonl(
            run_dir / "review_queue.jsonl",
            [record.model_dump(mode="json") for record in records],
        )
        return run_dir

    def write_validation_matrix(
        self,
        run_id: str,
        payload: dict,
    ) -> Path:
        run_dir = self.run_directory(run_id)
        self._write_json(
            run_dir / "validation_matrix.json",
            payload,
        )
        return run_dir

    def write_plan_result(self, run_id: str, result: PlanResult) -> Path:
        return self.write_context(
            run_id,
            agenda=result.agenda,
            hypothesis=result.hypothesis,
            blueprint=result.blueprint,
        )

    def write_synthesize_result(
        self,
        run_id: str,
        result: SynthesizeResult,
        *,
        agenda: ResearchAgenda | None = None,
    ) -> Path:
        self.write_context(
            run_id,
            agenda=agenda,
            hypothesis=result.hypothesis,
            blueprint=result.blueprint,
        )
        return self.write_candidate_records(
            run_id,
            records=[self._candidate_record_from_evaluation(evaluation) for evaluation in result.evaluations],
        )

    def write_simulation_result(self, run_id: str, result: SimulationOrchestratorResult) -> Path:
        self.write_context(
            run_id,
            agenda=None,
            hypothesis=result.hypothesis,
            blueprint=result.blueprint,
        )
        return self.write_simulation_records(
            run_id,
            records=[
                self._simulation_record_from_execution(execution)
                for execution in result.executions
            ],
        )

    def write_stage_a_result(self, run_id: str, result: StageAEvaluationResult) -> Path:
        self.write_context(
            run_id,
            agenda=None,
            hypothesis=result.hypothesis,
            blueprint=result.blueprint,
        )
        self.write_evaluation_records(
            run_id,
            records=[
                self._evaluation_record_from_outcome(outcome)
                for outcome in result.outcomes
            ],
        )
        return self.write_promotion_records(
            run_id,
            records=[
                self._promotion_record_from_outcome(outcome)
                for outcome in result.outcomes
            ],
        )

    def write_validation_result(
        self,
        run_id: str,
        result: ValidateResult | MultiPeriodValidateResult,
        *,
        agenda: ResearchAgenda | None = None,
    ) -> Path:
        self.write_context(
            run_id,
            agenda=agenda,
            hypothesis=result.hypothesis,
            blueprint=result.blueprint,
        )
        records = []
        if isinstance(result, MultiPeriodValidateResult):
            for period_result in result.period_results:
                records.extend(
                    self._validation_record_from_outcome(outcome)
                    for outcome in period_result.outcomes
                )
            self.write_validation_matrix(
                run_id,
                result.validation_matrix.model_dump(mode="json"),
            )
        else:
            records.extend(
                self._validation_record_from_outcome(outcome)
                for outcome in result.outcomes
            )

        return self.write_validation_records(
            run_id,
            records=records,
        )

    def write_robust_promotion_result(
        self,
        run_id: str,
        result: RobustPromotionResult,
    ) -> Path:
        return self.write_robust_promotion_records(
            run_id,
            records=[
                self._validation_promotion_record_from_outcome(
                    outcome,
                    validation_stage=result.validation_stage,
                )
                for outcome in result.outcomes
            ],
        )

    def write_submission_ready_result(
        self,
        run_id: str,
        result: SubmissionReadyPromotionResult,
        *,
        agenda: ResearchAgenda | None = None,
    ) -> Path:
        self.write_context(
            run_id,
            agenda=agenda,
            hypothesis=result.hypothesis,
            blueprint=result.blueprint,
        )
        return self.write_submission_ready_records(
            run_id,
            records=[
                self._submission_ready_record_from_outcome(outcome)
                for outcome in result.outcomes
            ],
        )

    def write_human_review_result(
        self,
        run_id: str,
        result: HumanReviewResult,
        *,
        queue_records: list[HumanReviewQueueRecord],
        agenda: ResearchAgenda | None = None,
    ) -> Path:
        self.write_context(
            run_id,
            agenda=agenda,
            hypothesis=result.hypothesis,
            blueprint=result.blueprint,
        )
        self.write_review_queue_records(
            run_id,
            records=queue_records,
        )
        return self.write_human_review_records(
            run_id,
            records=[
                self._human_review_record_from_outcome(outcome)
                for outcome in result.outcomes
            ],
        )

    def _candidate_record_from_evaluation(self, evaluation: CandidateEvaluation) -> CandidateArtifactRecord:
        return CandidateArtifactRecord(
            candidate=evaluation.candidate,
            validation=evaluation.validation,
            critique=evaluation.critique,
        )

    def _simulation_record_from_execution(
        self,
        execution: SimulationCandidateExecution,
    ) -> SimulationArtifactRecord:
        return SimulationArtifactRecord(
            simulation_request=execution.simulation_request,
            simulation_run=execution.simulation_run,
            submission=execution.submission,
            poll_history=execution.poll_history,
            result=execution.result,
        )

    def _evaluation_record_from_outcome(
        self,
        outcome: StageACandidateOutcome,
    ) -> EvaluationArtifactRecord:
        return EvaluationArtifactRecord(
            evaluation=outcome.evaluation,
            simulation_run=outcome.execution.simulation_run,
            result=outcome.execution.result,
        )

    def _promotion_record_from_outcome(
        self,
        outcome: StageACandidateOutcome,
    ) -> PromotionArtifactRecord:
        return PromotionArtifactRecord(
            evaluation=outcome.evaluation,
            promotion=outcome.promotion,
        )

    def _validation_record_from_outcome(
        self,
        outcome: ValidationOutcome,
    ) -> ValidationArtifactRecord:
        return ValidationArtifactRecord(
            candidate=outcome.candidate,
            validation=outcome.validation,
        )

    def _validation_promotion_record_from_outcome(
        self,
        outcome: RobustPromotionOutcome,
        *,
        validation_stage: str,
    ) -> ValidationPromotionArtifactRecord:
        return ValidationPromotionArtifactRecord(
            candidate=outcome.candidate,
            validation_stage=validation_stage,
            requested_periods=outcome.requested_periods,
            validation_ids=[
                validation.validation_id
                for validation in outcome.validation_records
            ],
            passing_periods=outcome.passing_periods,
            failing_periods=outcome.failing_periods,
            aggregate_pass_decision=outcome.aggregate_pass_decision,
            promotion=outcome.promotion,
        )

    def _submission_ready_record_from_outcome(
        self,
        outcome: SubmissionReadyPromotionOutcome,
    ) -> SubmissionReadyArtifactRecord:
        return SubmissionReadyArtifactRecord(
            candidate=outcome.robust_promotion.candidate,
            robust_promotion=outcome.robust_promotion,
            submission_promotion=outcome.submission_promotion,
        )

    def _human_review_record_from_outcome(
        self,
        outcome: HumanReviewOutcome,
    ) -> HumanReviewArtifactRecord:
        return HumanReviewArtifactRecord(
            submission_ready=outcome.submission_ready,
            review_decision=outcome.review_decision,
        )

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _write_jsonl(self, path: Path, payloads: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        rendered = "\n".join(json.dumps(payload) for payload in payloads)
        path.write_text(f"{rendered}\n" if rendered else "", encoding="utf-8")
