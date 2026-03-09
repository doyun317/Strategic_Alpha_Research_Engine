from __future__ import annotations

import json
from pathlib import Path

from strategic_alpha_engine.application.contracts import (
    AgendaQueueRecord,
    CandidateStageRecord,
    FamilyLearnerSummary,
    FamilyStatsSnapshot,
    HumanReviewQueueRecord,
    RunStateRecord,
    SubmissionReadyCandidateRecord,
    ValidationBacklogEntry,
)
from strategic_alpha_engine.domain.review import HumanReviewDecision


class LocalFileStateLedger:
    def __init__(self, root_dir: str | Path = "artifacts"):
        self.root_dir = Path(root_dir).expanduser().resolve()

    def state_directory(self) -> Path:
        path = self.root_dir / "state"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def append_candidate_stage_records(self, records: list[CandidateStageRecord]) -> Path:
        path = self.state_directory() / "candidate_stages.jsonl"
        self._append_jsonl(path, [record.model_dump(mode="json") for record in records])
        return path

    def append_run_state_records(self, records: list[RunStateRecord]) -> Path:
        path = self.state_directory() / "run_states.jsonl"
        self._append_jsonl(path, [record.model_dump(mode="json") for record in records])
        return path

    def append_agenda_queue_records(self, records: list[AgendaQueueRecord]) -> Path:
        path = self.state_directory() / "agenda_queue.jsonl"
        self._append_jsonl(path, [record.model_dump(mode="json") for record in records])
        return path

    def write_family_stats(self, snapshots: list[FamilyStatsSnapshot]) -> Path:
        path = self.state_directory() / "family_stats.json"
        payload = [snapshot.model_dump(mode="json") for snapshot in snapshots]
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def write_family_learner_summaries(self, summaries: list[FamilyLearnerSummary]) -> Path:
        path = self.state_directory() / "family_learner_summaries.json"
        payload = [summary.model_dump(mode="json") for summary in summaries]
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def append_validation_backlog_entries(self, entries: list[ValidationBacklogEntry]) -> Path:
        path = self.state_directory() / "validation_backlog.jsonl"
        self._append_jsonl(path, [entry.model_dump(mode="json") for entry in entries])
        return path

    def append_submission_ready_records(self, records: list[SubmissionReadyCandidateRecord]) -> Path:
        path = self.state_directory() / "submission_ready_candidates.jsonl"
        self._append_jsonl(path, [record.model_dump(mode="json") for record in records])
        return path

    def append_human_review_queue_records(self, records: list[HumanReviewQueueRecord]) -> Path:
        path = self.state_directory() / "human_review_queue.jsonl"
        self._append_jsonl(path, [record.model_dump(mode="json") for record in records])
        return path

    def append_human_review_decisions(self, records: list[HumanReviewDecision]) -> Path:
        path = self.state_directory() / "human_review_decisions.jsonl"
        self._append_jsonl(path, [record.model_dump(mode="json") for record in records])
        return path

    def load_candidate_stage_records(self) -> list[CandidateStageRecord]:
        path = self.state_directory() / "candidate_stages.jsonl"
        return [CandidateStageRecord(**payload) for payload in self._read_jsonl(path)]

    def load_run_state_records(self) -> list[RunStateRecord]:
        path = self.state_directory() / "run_states.jsonl"
        return [RunStateRecord(**payload) for payload in self._read_jsonl(path)]

    def load_agenda_queue_records(self) -> list[AgendaQueueRecord]:
        path = self.state_directory() / "agenda_queue.jsonl"
        return [AgendaQueueRecord(**payload) for payload in self._read_jsonl(path)]

    def load_family_stats(self) -> list[FamilyStatsSnapshot]:
        path = self.state_directory() / "family_stats.json"
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [FamilyStatsSnapshot(**item) for item in payload]

    def load_family_learner_summaries(self) -> list[FamilyLearnerSummary]:
        path = self.state_directory() / "family_learner_summaries.json"
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [FamilyLearnerSummary(**item) for item in payload]

    def load_validation_backlog_entries(self) -> list[ValidationBacklogEntry]:
        path = self.state_directory() / "validation_backlog.jsonl"
        return [ValidationBacklogEntry(**payload) for payload in self._read_jsonl(path)]

    def load_submission_ready_records(self) -> list[SubmissionReadyCandidateRecord]:
        path = self.state_directory() / "submission_ready_candidates.jsonl"
        return [SubmissionReadyCandidateRecord(**payload) for payload in self._read_jsonl(path)]

    def load_human_review_queue_records(self) -> list[HumanReviewQueueRecord]:
        path = self.state_directory() / "human_review_queue.jsonl"
        return [HumanReviewQueueRecord(**payload) for payload in self._read_jsonl(path)]

    def load_human_review_decisions(self) -> list[HumanReviewDecision]:
        path = self.state_directory() / "human_review_decisions.jsonl"
        return [HumanReviewDecision(**payload) for payload in self._read_jsonl(path)]

    def _append_jsonl(self, path: Path, payloads: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        rendered = "\n".join(json.dumps(payload) for payload in payloads)
        if not rendered:
            return
        path.write_text(f"{existing}{rendered}\n", encoding="utf-8")

    def _read_jsonl(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return []
        return [json.loads(line) for line in content.splitlines()]
