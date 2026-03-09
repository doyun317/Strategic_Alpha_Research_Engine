from __future__ import annotations

import json
from pathlib import Path

from strategic_alpha_engine.application.contracts import (
    CandidateStageRecord,
    FamilyStatsSnapshot,
    RunStateRecord,
    ValidationBacklogEntry,
)


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

    def write_family_stats(self, snapshots: list[FamilyStatsSnapshot]) -> Path:
        path = self.state_directory() / "family_stats.json"
        payload = [snapshot.model_dump(mode="json") for snapshot in snapshots]
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def append_validation_backlog_entries(self, entries: list[ValidationBacklogEntry]) -> Path:
        path = self.state_directory() / "validation_backlog.jsonl"
        self._append_jsonl(path, [entry.model_dump(mode="json") for entry in entries])
        return path

    def load_candidate_stage_records(self) -> list[CandidateStageRecord]:
        path = self.state_directory() / "candidate_stages.jsonl"
        return [CandidateStageRecord(**payload) for payload in self._read_jsonl(path)]

    def load_run_state_records(self) -> list[RunStateRecord]:
        path = self.state_directory() / "run_states.jsonl"
        return [RunStateRecord(**payload) for payload in self._read_jsonl(path)]

    def load_family_stats(self) -> list[FamilyStatsSnapshot]:
        path = self.state_directory() / "family_stats.json"
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [FamilyStatsSnapshot(**item) for item in payload]

    def load_validation_backlog_entries(self) -> list[ValidationBacklogEntry]:
        path = self.state_directory() / "validation_backlog.jsonl"
        return [ValidationBacklogEntry(**payload) for payload in self._read_jsonl(path)]

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
