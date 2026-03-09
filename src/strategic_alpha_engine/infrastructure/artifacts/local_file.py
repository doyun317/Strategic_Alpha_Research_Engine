from __future__ import annotations

import json
from pathlib import Path

from strategic_alpha_engine.application.contracts import CandidateArtifactRecord, SimulationArtifactRecord
from strategic_alpha_engine.application.workflows.plan import PlanResult
from strategic_alpha_engine.application.workflows.simulate import (
    SimulationCandidateExecution,
    SimulationOrchestratorResult,
)
from strategic_alpha_engine.application.workflows.synthesize import CandidateEvaluation, SynthesizeResult
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
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

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _write_jsonl(self, path: Path, payloads: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        rendered = "\n".join(json.dumps(payload) for payload in payloads)
        path.write_text(f"{rendered}\n" if rendered else "", encoding="utf-8")
