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
    assert payload["promoted_candidate_ids"] == payload["simulated_candidate_ids"]
    assert payload["family_learner_summary"]["stage_a_pass_rate"] == 1.0
    assert run_dir.exists()
    assert (run_dir / "agenda.json").exists()
    assert (run_dir / "candidates.jsonl").exists()
    assert (run_dir / "simulations.jsonl").exists()
    assert (run_dir / "evaluations.jsonl").exists()
    assert (run_dir / "promotion.jsonl").exists()
    assert state_dir.exists()
    assert (state_dir / "candidate_stages.jsonl").exists()
    assert (state_dir / "run_states.jsonl").exists()
    assert (state_dir / "family_stats.json").exists()
    assert (state_dir / "family_learner_summaries.json").exists()


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
    assert payload["agenda_queue"]["total_entries"] == 0
    assert payload["candidate_stage_counts"]["sim_passed"] == 4
    assert payload["runs"]["counts_by_kind"]["simulate"] == 1
    assert payload["family_stats"][0]["sim_passed_candidates"] == 4
    assert payload["family_stats"][0]["median_stage_a_sharpe"] == 1.21
    assert payload["family_learner_summaries"][0]["stage_a_pass_rate"] == 1.0
    assert payload["learner_recommendations"][0]["family"] == "quality_deterioration"
    assert payload["validation_summary"]["total_records"] == 0
    assert payload["validation_matrix"]["total_candidates"] == 0
    assert payload["robust_promotion_summary"]["total_decisions"] == 0
    assert payload["submission_ready_inventory"]["total_candidates"] == 0
    assert payload["human_review_queue"]["total_entries"] == 0
    assert payload["human_review_summary"]["total_decisions"] == 0


def test_policy_command_ranks_families_and_weights_agendas(tmp_path, capsys):
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
    quality_agenda_path = tmp_path / "quality_agenda.json"
    momentum_agenda_path = tmp_path / "momentum_agenda.json"
    quality_agenda_path.write_text(
        json.dumps(build_sample_research_agenda().model_dump(mode="json")),
        encoding="utf-8",
    )
    momentum_agenda_path.write_text(
        json.dumps(
            build_sample_research_agenda().model_copy(
                update={
                    "agenda_id": "agenda.momentum.001",
                    "name": "Momentum continuation queue",
                    "family": "momentum",
                    "priority": 0.65,
                    "tags": ["momentum", "medium_horizon"],
                }
            ).model_dump(mode="json")
        ),
        encoding="utf-8",
    )

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

    exit_code = main(
        [
            "policy",
            "--artifacts-dir",
            str(artifacts_dir),
            "--agenda-in",
            str(quality_agenda_path),
            "--agenda-in",
            str(momentum_agenda_path),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert simulate_exit_code == 0
    assert exit_code == 0
    assert payload["family_recommendations"][0]["family"] == "quality_deterioration"
    assert payload["agenda_recommendations"][0]["agenda_id"] == "agenda.quality_deterioration.001"
    assert payload["agenda_recommendations"][0]["adjusted_priority"] > payload["agenda_recommendations"][1]["adjusted_priority"]


def test_research_loop_command_executes_multiple_iterations_and_updates_queue_state(tmp_path, capsys):
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

    exit_code = main(
        [
            "research-loop",
            "--settings-dir",
            str(settings_dir),
            "--artifacts-dir",
            str(artifacts_dir),
            "--iterations",
            "2",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["completed_iterations"] == 2
    assert payload["stopped_reason"] == "completed_requested_iterations"
    assert payload["iteration_runs"][0]["selected_agenda_id"] == "agenda.quality_deterioration.001"
    assert payload["iteration_runs"][1]["selected_agenda_id"] == "agenda.momentum.001"
    assert payload["executed_agenda_ids"] == [
        "agenda.quality_deterioration.001",
        "agenda.momentum.001",
    ]

    status_exit_code = main(["status", "--artifacts-dir", str(artifacts_dir)])
    status_captured = capsys.readouterr()
    status_payload = json.loads(status_captured.out)

    assert status_exit_code == 0
    assert status_payload["loop_status"]["current_state"] == "idle"
    assert status_payload["runs"]["counts_by_kind"]["research_loop"] == 2
    assert status_payload["agenda_queue"]["selected_agenda_id"] == "agenda.momentum.001"
    assert status_payload["agenda_queue"]["total_entries"] == 3
    assert status_payload["candidate_stage_counts"]["sim_passed"] == 7
    assert status_payload["validation_matrix"]["total_candidates"] == 0
    assert status_payload["robust_promotion_summary"]["total_decisions"] == 0
    assert status_payload["submission_ready_inventory"]["total_candidates"] == 0
    assert status_payload["human_review_queue"]["total_entries"] == 0


def test_validate_command_persists_validation_artifacts_and_updates_status(tmp_path, capsys):
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
    simulate_captured = capsys.readouterr()
    simulate_payload = json.loads(simulate_captured.out)

    validate_exit_code = main(
        [
            "validate",
            "--artifacts-dir",
            str(artifacts_dir),
            "--source-run-id",
            simulate_payload["run_id"],
            "--period",
            "P3Y0M0D",
        ]
    )
    validate_captured = capsys.readouterr()
    validate_payload = json.loads(validate_captured.out)

    status_exit_code = main(["status", "--artifacts-dir", str(artifacts_dir)])
    status_captured = capsys.readouterr()
    status_payload = json.loads(status_captured.out)

    run_dir = artifacts_dir / "runs" / validate_payload["run_id"]

    assert simulate_exit_code == 0
    assert validate_exit_code == 0
    assert status_exit_code == 0
    assert validate_payload["validation_stage"] == "stage_b"
    assert validate_payload["requested_periods"] == ["P3Y0M0D"]
    assert len(validate_payload["validated_candidate_ids"]) == 4
    assert validate_payload["passed_candidate_ids"] == validate_payload["validated_candidate_ids"]
    assert (run_dir / "validations.jsonl").exists()
    assert (run_dir / "robust_promotion.jsonl").exists()
    assert validate_payload["validation_matrix"]["required_passing_periods"] == 1
    assert validate_payload["robust_promoted_candidate_ids"] == [
        "cand.bp.quality_deterioration.001.001",
        "cand.bp.quality_deterioration.001.002",
    ]
    assert len(validate_payload["robust_held_candidate_ids"]) == 2
    assert validate_payload["robust_rejected_candidate_ids"] == []
    assert validate_payload["robust_promotion_summary"]["counts_by_decision"]["hold"] == 2
    assert validate_payload["robust_promotion_summary"]["counts_by_decision"]["promote"] == 2
    assert status_payload["validation_backlog"]["counts_by_status"]["completed"] == 4
    assert status_payload["validation_summary"]["total_records"] == 4
    assert status_payload["validation_summary"]["counts_by_stage"]["stage_b"] == 4
    assert status_payload["validation_matrix"]["total_candidates"] == 4
    assert status_payload["validation_matrix"]["required_passing_periods"] == 1
    assert status_payload["robust_promotion_summary"]["counts_by_decision"]["hold"] == 2
    assert status_payload["robust_promotion_summary"]["counts_by_decision"]["promote"] == 2
    assert status_payload["candidate_stage_counts"]["robust_candidate"] == 2
    assert status_payload["candidate_stage_counts"]["sim_passed"] == 2
    assert status_payload["family_stats"][0]["robust_candidates"] == 2
    assert status_payload["runs"]["counts_by_kind"]["validate"] == 1


def test_validate_command_defaults_to_multi_period_stage_b(tmp_path, capsys):
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
    simulate_captured = capsys.readouterr()
    simulate_payload = json.loads(simulate_captured.out)

    validate_exit_code = main(
        [
            "validate",
            "--artifacts-dir",
            str(artifacts_dir),
            "--source-run-id",
            simulate_payload["run_id"],
        ]
    )
    validate_captured = capsys.readouterr()
    validate_payload = json.loads(validate_captured.out)

    status_exit_code = main(["status", "--artifacts-dir", str(artifacts_dir)])
    status_captured = capsys.readouterr()
    status_payload = json.loads(status_captured.out)

    assert simulate_exit_code == 0
    assert validate_exit_code == 0
    assert status_exit_code == 0
    assert validate_payload["requested_periods"] == ["P1Y0M0D", "P3Y0M0D", "P5Y0M0D"]
    assert validate_payload["validation_summary"]["total_records"] == 12
    assert validate_payload["validation_matrix"]["required_passing_periods"] == 2
    assert validate_payload["validation_matrix"]["total_candidates"] == 4
    assert validate_payload["robust_promoted_candidate_ids"] == [
        "cand.bp.quality_deterioration.001.001",
        "cand.bp.quality_deterioration.001.002",
    ]
    assert len(validate_payload["robust_held_candidate_ids"]) == 2
    assert status_payload["validation_backlog"]["counts_by_status"]["completed"] == 12
    assert status_payload["validation_summary"]["total_records"] == 12
    assert status_payload["validation_summary"]["counts_by_period"]["P5Y0M0D"] == 4
    assert status_payload["validation_matrix"]["required_passing_periods"] == 2
    assert status_payload["validation_matrix"]["passed_candidate_count"] == 4
    assert status_payload["robust_promotion_summary"]["counts_by_decision"]["promote"] == 2
    assert status_payload["robust_promotion_summary"]["counts_by_decision"]["hold"] == 2
    assert status_payload["candidate_stage_counts"]["robust_candidate"] == 2
    assert status_payload["candidate_stage_counts"]["sim_passed"] == 2


def test_validate_command_uses_latest_stage_state_and_does_not_repromote_duplicates(tmp_path, capsys):
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
    simulate_captured = capsys.readouterr()
    simulate_payload = json.loads(simulate_captured.out)

    first_validate_exit_code = main(
        [
            "validate",
            "--artifacts-dir",
            str(artifacts_dir),
            "--source-run-id",
            simulate_payload["run_id"],
        ]
    )
    first_validate_captured = capsys.readouterr()
    first_validate_payload = json.loads(first_validate_captured.out)

    second_validate_exit_code = main(
        [
            "validate",
            "--artifacts-dir",
            str(artifacts_dir),
            "--source-run-id",
            simulate_payload["run_id"],
        ]
    )
    second_validate_captured = capsys.readouterr()
    second_validate_payload = json.loads(second_validate_captured.out)

    status_exit_code = main(["status", "--artifacts-dir", str(artifacts_dir)])
    status_captured = capsys.readouterr()
    status_payload = json.loads(status_captured.out)

    assert simulate_exit_code == 0
    assert first_validate_exit_code == 0
    assert second_validate_exit_code == 0
    assert first_validate_payload["robust_promoted_candidate_ids"] == [
        "cand.bp.quality_deterioration.001.001",
        "cand.bp.quality_deterioration.001.002",
    ]
    assert second_validate_payload["validated_candidate_ids"] == [
        "cand.bp.quality_deterioration.001.003",
        "cand.bp.quality_deterioration.001.004",
    ]
    assert second_validate_payload["robust_promoted_candidate_ids"] == []
    assert len(second_validate_payload["robust_held_candidate_ids"]) == 2
    assert status_exit_code == 0
    assert status_payload["candidate_stage_counts"]["robust_candidate"] == 2


def test_promote_command_creates_submission_ready_inventory_and_updates_status(tmp_path, capsys):
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
    simulate_payload = json.loads(capsys.readouterr().out)

    validate_exit_code = main(
        [
            "validate",
            "--artifacts-dir",
            str(artifacts_dir),
            "--source-run-id",
            simulate_payload["run_id"],
        ]
    )
    validate_payload = json.loads(capsys.readouterr().out)

    promote_exit_code = main(
        [
            "promote",
            "--artifacts-dir",
            str(artifacts_dir),
            "--source-run-id",
            validate_payload["run_id"],
        ]
    )
    promote_payload = json.loads(capsys.readouterr().out)

    status_exit_code = main(["status", "--artifacts-dir", str(artifacts_dir)])
    status_payload = json.loads(capsys.readouterr().out)

    run_dir = artifacts_dir / "runs" / promote_payload["run_id"]

    assert simulate_exit_code == 0
    assert validate_exit_code == 0
    assert promote_exit_code == 0
    assert status_exit_code == 0
    assert promote_payload["source_validate_run_id"] == validate_payload["run_id"]
    assert promote_payload["submission_ready_candidate_ids"] == [
        "cand.bp.quality_deterioration.001.001",
        "cand.bp.quality_deterioration.001.002",
    ]
    assert promote_payload["queued_review_candidate_ids"] == promote_payload["submission_ready_candidate_ids"]
    assert (run_dir / "submission_ready.jsonl").exists()
    assert promote_payload["submission_ready_inventory"]["total_candidates"] == 2
    assert promote_payload["human_review_queue"]["counts_by_status"]["pending"] == 2
    assert status_payload["submission_ready_inventory"]["total_candidates"] == 2
    assert status_payload["submission_ready_inventory"]["latest_run_id"] == promote_payload["run_id"]
    assert status_payload["human_review_queue"]["counts_by_status"]["pending"] == 2
    assert status_payload["candidate_stage_counts"]["submission_ready"] == 2
    assert status_payload["candidate_stage_counts"]["robust_candidate"] == 0
    assert status_payload["candidate_stage_counts"]["sim_passed"] == 2
    assert status_payload["family_stats"][0]["submission_ready_candidates"] == 2
    assert status_payload["runs"]["counts_by_kind"]["promote"] == 1


def test_review_command_holds_submission_ready_candidate_and_filters_inventory(tmp_path, capsys):
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
    simulate_payload = json.loads(capsys.readouterr().out)

    validate_exit_code = main(
        [
            "validate",
            "--artifacts-dir",
            str(artifacts_dir),
            "--source-run-id",
            simulate_payload["run_id"],
        ]
    )
    validate_payload = json.loads(capsys.readouterr().out)

    promote_exit_code = main(
        [
            "promote",
            "--artifacts-dir",
            str(artifacts_dir),
            "--source-run-id",
            validate_payload["run_id"],
        ]
    )
    promote_payload = json.loads(capsys.readouterr().out)

    review_exit_code = main(
        [
            "review",
            "--artifacts-dir",
            str(artifacts_dir),
            "--source-run-id",
            promote_payload["run_id"],
            "--candidate-id",
            "cand.bp.quality_deterioration.001.001",
            "--decision",
            "hold",
            "--reviewer",
            "reviewer_01",
            "--note",
            "needs manual follow-up",
        ]
    )
    review_payload = json.loads(capsys.readouterr().out)

    status_exit_code = main(["status", "--artifacts-dir", str(artifacts_dir)])
    status_payload = json.loads(capsys.readouterr().out)

    run_dir = artifacts_dir / "runs" / review_payload["run_id"]

    assert simulate_exit_code == 0
    assert validate_exit_code == 0
    assert promote_exit_code == 0
    assert review_exit_code == 0
    assert status_exit_code == 0
    assert review_payload["held_candidate_ids"] == ["cand.bp.quality_deterioration.001.001"]
    assert review_payload["approved_candidate_ids"] == []
    assert review_payload["submission_ready_inventory"]["total_candidates"] == 1
    assert review_payload["human_review_queue"]["counts_by_status"]["held"] == 1
    assert review_payload["human_review_queue"]["counts_by_status"]["pending"] == 1
    assert review_payload["human_review_summary"]["counts_by_decision"]["hold"] == 1
    assert (run_dir / "human_review.jsonl").exists()
    assert (run_dir / "review_queue.jsonl").exists()
    assert status_payload["submission_ready_inventory"]["total_candidates"] == 1
    assert status_payload["human_review_queue"]["counts_by_status"]["held"] == 1
    assert status_payload["human_review_queue"]["counts_by_status"]["pending"] == 1
    assert status_payload["candidate_stage_counts"]["submission_ready"] == 1
    assert status_payload["candidate_stage_counts"]["robust_candidate"] == 1
    assert status_payload["family_stats"][0]["submission_ready_candidates"] == 1
    assert status_payload["family_stats"][0]["robust_candidates"] == 2
    assert status_payload["runs"]["counts_by_kind"]["review"] == 1
