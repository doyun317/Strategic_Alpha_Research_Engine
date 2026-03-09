import json

import pytest

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
