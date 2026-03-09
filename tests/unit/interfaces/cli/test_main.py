import json

import pytest

from strategic_alpha_engine.domain.examples import (
    build_sample_hypothesis_spec,
    build_sample_research_agenda,
    build_sample_signal_blueprint,
)
from strategic_alpha_engine.interfaces.cli.main import main


def test_config_command_prints_runtime_settings(tmp_path, capsys):
    (tmp_path / "default.env").write_text(
        "\n".join(
            [
                "SAE_ENV=development",
                "SAE_LOG_LEVEL=INFO",
                "SAE_REGION=USA",
                "SAE_UNIVERSE=TOP3000",
                "SAE_DEFAULT_TEST_PERIOD=P1Y0M0D",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(["config", "--settings-dir", str(tmp_path)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["region"] == "USA"
    assert payload["loaded_env_files"] == ["default.env"]


def test_config_command_reports_missing_required_brain_settings(tmp_path, capsys):
    (tmp_path / "default.env").write_text("SAE_ENV=development\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(["config", "--settings-dir", str(tmp_path), "--require-brain"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 2
    assert "Brain settings are required" in captured.err


def test_catalog_command_prints_summary(capsys):
    exit_code = main(["catalog", "--view", "summary"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["field_count"] >= 1
    assert "close" in payload["field_ids"]


def test_example_command_prints_static_validation_payload(capsys):
    exit_code = main(["example", "--model", "static_validation"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["passes"] is True
    assert payload["validator_name"] == "metadata_backed_static_validator"


def test_prompt_command_prints_planner_asset(capsys):
    exit_code = main(["prompt", "--role", "planner"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["prompt_id"] == "planner.default.v1"
    assert payload["role"] == "planner"


def test_prompt_command_prints_requested_golden_sample(capsys):
    exit_code = main(["prompt", "--role", "critic", "--sample-id", "critic.quality_deterioration.001"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["sample_id"] == "critic.quality_deterioration.001"
    assert payload["role"] == "critic"


def test_plan_command_prints_plan_result(capsys):
    exit_code = main(["plan"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["agenda"]["agenda_id"] == "agenda.quality_deterioration.001"
    assert payload["blueprint"]["hypothesis_id"] == payload["hypothesis"]["hypothesis_id"]


def test_plan_command_reads_agenda_file(tmp_path, capsys):
    agenda_path = tmp_path / "agenda.json"
    agenda_path.write_text(
        json.dumps(build_sample_research_agenda().model_dump(mode="json")),
        encoding="utf-8",
    )

    exit_code = main(["plan", "--agenda-in", str(agenda_path)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["agenda"]["agenda_id"] == "agenda.quality_deterioration.001"
    assert payload["hypothesis"]["agenda_id"] == payload["agenda"]["agenda_id"]


def test_plan_command_writes_output_file(tmp_path, capsys):
    output_path = tmp_path / "artifacts" / "plan.json"

    exit_code = main(["plan", "--out", str(output_path)])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert captured.out == ""
    assert payload["blueprint"]["blueprint_id"] == "bp.quality_deterioration.001"


def test_synthesize_command_reads_plan_file(tmp_path, capsys):
    plan_payload = {
        "agenda": build_sample_research_agenda().model_dump(mode="json"),
        "hypothesis": build_sample_hypothesis_spec().model_dump(mode="json"),
        "blueprint": build_sample_signal_blueprint().model_dump(mode="json"),
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")

    exit_code = main(["synthesize", "--plan-in", str(plan_path)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["hypothesis"]["hypothesis_id"] == "hyp.quality_deterioration.001"
    assert len(payload["evaluations"]) == 4


def test_synthesize_command_reads_hypothesis_and_blueprint_files(tmp_path, capsys):
    hypothesis_path = tmp_path / "hypothesis.json"
    blueprint_path = tmp_path / "blueprint.json"
    hypothesis_path.write_text(
        json.dumps(build_sample_hypothesis_spec().model_dump(mode="json")),
        encoding="utf-8",
    )
    blueprint_path.write_text(
        json.dumps(build_sample_signal_blueprint().model_dump(mode="json")),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "synthesize",
            "--hypothesis-in",
            str(hypothesis_path),
            "--blueprint-in",
            str(blueprint_path),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["blueprint"]["blueprint_id"] == "bp.quality_deterioration.001"
    assert payload["hypothesis"]["agenda_id"] == "agenda.quality_deterioration.001"
    assert len(payload["accepted_candidate_ids"]) + len(payload["rejected_candidate_ids"]) == len(
        payload["evaluations"]
    )


def test_simulate_command_persists_artifacts_and_state(tmp_path, capsys):
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    (settings_dir / "default.env").write_text(
        "\n".join(
            [
                "SAE_ENV=test",
                "SAE_REGION=USA",
                "SAE_UNIVERSE=TOP3000",
                "SAE_DEFAULT_TEST_PERIOD=P2Y0M0D",
                "SAE_SIMULATION_DELAY=1",
                "SAE_SIMULATION_NEUTRALIZATION=subindustry",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    artifacts_dir = tmp_path / "artifacts"

    exit_code = main(
        [
            "simulate",
            "--settings-dir",
            str(settings_dir),
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    run_dir = artifacts_dir / "runs" / payload["run_id"]
    state_dir = artifacts_dir / "state"

    assert exit_code == 0
    assert payload["family"] == "quality_deterioration"
    assert payload["policy"]["test_period"] == "P2Y0M0D"
    assert payload["simulation_status_counts"]["succeeded"] == len(payload["simulated_candidate_ids"])
    assert run_dir.exists()
    assert (run_dir / "agenda.json").exists()
    assert (run_dir / "candidates.jsonl").exists()
    assert (run_dir / "simulations.jsonl").exists()
    assert state_dir.exists()
    assert (state_dir / "candidate_stages.jsonl").exists()
    assert (state_dir / "run_states.jsonl").exists()
    assert (state_dir / "family_stats.json").exists()


def test_status_command_summarizes_local_ledgers(tmp_path, capsys):
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    (settings_dir / "default.env").write_text(
        "\n".join(
            [
                "SAE_ENV=test",
                "SAE_REGION=USA",
                "SAE_UNIVERSE=TOP3000",
                "SAE_DEFAULT_TEST_PERIOD=P1Y0M0D",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    artifacts_dir = tmp_path / "artifacts"

    simulate_exit_code = main(
        [
            "simulate",
            "--settings-dir",
            str(settings_dir),
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )
    _ = capsys.readouterr()

    exit_code = main(["status", "--artifacts-dir", str(artifacts_dir)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert simulate_exit_code == 0
    assert exit_code == 0
    assert payload["loop_status"]["current_state"] == "not_started"
    assert payload["agenda_status"]["latest_family"] == "quality_deterioration"
    assert payload["validation_backlog"]["total_entries"] == 0
    assert payload["candidate_stage_counts"]["sim_passed"] == 4
    assert payload["runs"]["counts_by_kind"]["simulate"] == 1
    assert payload["family_stats"][0]["sim_passed_candidates"] == 4
