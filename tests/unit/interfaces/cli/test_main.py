import json

import pytest

from strategic_alpha_engine.domain import ExpressionCandidate, HypothesisSpec, ResearchAgenda, SignalBlueprint
from strategic_alpha_engine.domain.critique_report import CritiqueReport
from strategic_alpha_engine.domain.examples import (
    build_sample_critique_report,
    build_sample_hypothesis_spec,
    build_sample_research_agenda,
    build_sample_signal_blueprint,
)
from strategic_alpha_engine.interfaces.cli.main import main


REMOVED_MANUAL_COMMANDS = [
    "research-once",
    "plan",
    "synthesize",
    "simulate",
    "validate",
    "promote",
    "review",
    "packet",
    "policy",
    "research-loop",
]


def _write_default_settings(settings_dir, *, include_llm: bool = False, include_brain: bool = False) -> None:
    settings_dir.mkdir(exist_ok=True)
    (settings_dir / "default.env").write_text(
        "\n".join(
            [
                "SAE_ENV=test",
                "SAE_LOG_LEVEL=INFO",
                "SAE_REGION=USA",
                "SAE_UNIVERSE=TOP3000",
                "SAE_DEFAULT_TEST_PERIOD=P1Y0M0D",
                "SAE_SIMULATION_DELAY=1",
                "SAE_SIMULATION_NEUTRALIZATION=subindustry",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if include_llm:
        (settings_dir / "llm.env").write_text(
            "\n".join(
                [
                    "SAE_LLM_BASE_URL=http://127.0.0.1:8000/v1",
                    "SAE_LLM_MODEL=test-model",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    if include_brain:
        (settings_dir / "brain.env").write_text(
            "\n".join(
                [
                    "SAE_BRAIN_BASE_URL=https://api.worldquantbrain.com",
                    "SAE_BRAIN_USERNAME=tester@example.com",
                    "SAE_BRAIN_PASSWORD=super-secret",
                ]
            )
            + "\n",
            encoding="utf-8",
        )


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _build_hypothesis_for_agenda(agenda: ResearchAgenda) -> HypothesisSpec:
    sample = build_sample_hypothesis_spec()
    family_value = _enum_value(agenda.family)
    return sample.model_copy(
        update={
            "hypothesis_id": "hyp.autopilot.001",
            "agenda_id": agenda.agenda_id,
            "family": agenda.family,
            "horizon": agenda.target_horizons[0],
            "target_region": agenda.target_region,
            "target_universe": agenda.target_universe,
            "thesis_name": f"{family_value.replace('_', ' ')} autopilot hypothesis",
            "author": "autopilot",
        }
    )


def _build_blueprint_for_hypothesis(hypothesis: HypothesisSpec) -> SignalBlueprint:
    sample = build_sample_signal_blueprint()
    family_value = _enum_value(hypothesis.family)
    return sample.model_copy(
        update={
            "blueprint_id": "bp.autopilot.001",
            "hypothesis_id": hypothesis.hypothesis_id,
            "summary": f"Autopilot blueprint for {family_value}.",
        }
    )


def _build_critique_for_candidate(candidate: ExpressionCandidate, blueprint: SignalBlueprint) -> CritiqueReport:
    sample = build_sample_critique_report()
    return sample.model_copy(
        update={
            "critique_id": f"critique.{candidate.candidate_id}",
            "candidate_id": candidate.candidate_id,
            "blueprint_id": blueprint.blueprint_id,
        }
    )


class StubStructuredLLMClient:
    def generate_structured(self, *, asset, input_payload, output_model):
        if asset.role == "agenda_generator":
            return output_model(agendas=[], generator_notes=["stub_agenda_generator"])

        if asset.role == "planner":
            agenda = ResearchAgenda(**input_payload["agenda"])
            return output_model(
                hypothesis=_build_hypothesis_for_agenda(agenda),
                planner_notes=["stubbed_planner"],
            )

        if asset.role == "blueprint":
            hypothesis = HypothesisSpec(**input_payload["hypothesis"])
            return output_model(
                blueprint=_build_blueprint_for_hypothesis(hypothesis),
                design_notes=["stubbed_blueprint"],
            )

        hypothesis = HypothesisSpec(**input_payload["hypothesis"])
        blueprint = SignalBlueprint(**input_payload["blueprint"])
        candidate = ExpressionCandidate(
            **{
                key: value
                for key, value in input_payload["candidate"].items()
                if key in ExpressionCandidate.model_fields
            }
        )
        return output_model(
            critique=_build_critique_for_candidate(candidate, blueprint),
        )


def _run_fake_autopilot(tmp_path, monkeypatch, capsys):
    settings_dir = tmp_path / "settings"
    artifacts_dir = tmp_path / "artifacts"
    agenda_path = tmp_path / "agenda.json"

    _write_default_settings(settings_dir, include_llm=True)
    agenda_path.write_text(
        json.dumps(build_sample_research_agenda().model_dump(mode="json")),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "strategic_alpha_engine.interfaces.cli.autopilot_runtime.build_structured_llm_client",
        lambda settings: StubStructuredLLMClient(),
    )

    exit_code = main(
        [
            "autopilot",
            "--settings-dir",
            str(settings_dir),
            "--artifacts-dir",
            str(artifacts_dir),
            "--agenda-catalog-in",
            str(agenda_path),
            "--brain-provider",
            "fake",
            "--target-packet-count",
            "1",
            "--packet-top-k",
            "1",
            "--max-agendas",
            "1",
            "--max-simulations",
            "1",
            "--idle-rounds",
            "1",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    return exit_code, payload, artifacts_dir


def test_config_command_prints_runtime_settings(tmp_path, capsys):
    _write_default_settings(tmp_path)

    exit_code = main(["config", "--settings-dir", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["region"] == "USA"
    assert payload["loaded_env_files"] == ["default.env"]


def test_config_command_redacts_brain_password(tmp_path, capsys):
    _write_default_settings(tmp_path, include_brain=True)

    exit_code = main(["config", "--settings-dir", str(tmp_path), "--require-brain"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["brain"]["base_url"] == "https://api.worldquantbrain.com"
    assert payload["brain"]["username"] == "tester@example.com"
    assert payload["brain"]["password_configured"] is True
    assert "password" not in payload["brain"]


def test_config_command_reports_missing_required_brain_settings(tmp_path, capsys):
    _write_default_settings(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        main(["config", "--settings-dir", str(tmp_path), "--require-brain"])

    assert exc_info.value.code == 2
    assert "Brain settings are required" in capsys.readouterr().err


def test_catalog_command_prints_summary(capsys):
    exit_code = main(["catalog", "--view", "summary"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["field_count"] >= 1
    assert "close" in payload["field_ids"]


def test_schema_command_prints_candidate_schema(capsys):
    exit_code = main(["schema", "--model", "candidate"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["title"] == "ExpressionCandidate"
    assert "properties" in payload


def test_example_command_prints_static_validation_payload(capsys):
    exit_code = main(["example", "--model", "static_validation"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["passes"] is True
    assert payload["validator_name"] == "metadata_backed_static_validator"


def test_prompt_command_prints_planner_asset(capsys):
    exit_code = main(["prompt", "--role", "planner"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["prompt_id"] == "planner.default.v1"
    assert payload["role"] == "planner"


def test_prompt_command_prints_agenda_generator_asset(capsys):
    exit_code = main(["prompt", "--role", "agenda_generator"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["prompt_id"] == "agenda_generator.default.v1"
    assert payload["role"] == "agenda_generator"


def test_prompt_command_prints_requested_golden_sample(capsys):
    exit_code = main(["prompt", "--role", "critic", "--sample-id", "critic.quality_deterioration.001"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["sample_id"] == "critic.quality_deterioration.001"
    assert payload["role"] == "critic"


@pytest.mark.parametrize("command", REMOVED_MANUAL_COMMANDS)
def test_removed_manual_commands_are_invalid_choices(command, capsys):
    with pytest.raises(SystemExit) as exc_info:
        main([command])

    assert exc_info.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_autopilot_command_runs_full_fake_pipeline(tmp_path, capsys, monkeypatch):
    exit_code, payload, artifacts_dir = _run_fake_autopilot(tmp_path, monkeypatch, capsys)

    assert exit_code == 0
    assert payload["latest_submission_manifest"]["selected_packet_count"] == 1
    assert len(payload["packet_ids"]) == 1
    assert (artifacts_dir / "state" / "latest_submission_manifest.json").exists()
    assert (artifacts_dir / "state" / "submission_packet_index.jsonl").exists()


def test_status_command_reports_autopilot_summary(tmp_path, capsys, monkeypatch):
    autopilot_exit_code, autopilot_payload, artifacts_dir = _run_fake_autopilot(
        tmp_path,
        monkeypatch,
        capsys,
    )

    status_exit_code = main(["status", "--artifacts-dir", str(artifacts_dir)])
    status_payload = json.loads(capsys.readouterr().out)

    assert autopilot_exit_code == 0
    assert status_exit_code == 0
    assert status_payload["autopilot_status"]["current_state"] == "idle"
    assert status_payload["autopilot_status"]["latest_run_id"] == autopilot_payload["run_id"]
    assert status_payload["autopilot_status"]["ready_for_submission_packet_count"] == 1
    assert status_payload["latest_submission_manifest"]["selected_packet_count"] == 1
    assert status_payload["submission_packet_index"]["unique_signatures"] >= 1
    assert status_payload["runs"]["counts_by_kind"]["autopilot"] == 1
