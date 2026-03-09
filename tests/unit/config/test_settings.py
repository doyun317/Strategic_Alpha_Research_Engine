import pytest

from strategic_alpha_engine.config import load_runtime_settings


def test_load_runtime_settings_merges_env_files(tmp_path):
    (tmp_path / "default.env").write_text(
        "\n".join(
            [
                "SAE_ENV=development",
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
    (tmp_path / "local.env").write_text("SAE_LOG_LEVEL=DEBUG\nSAE_UNIVERSE=TOP1000\n", encoding="utf-8")
    (tmp_path / "llm.env").write_text(
        "\n".join(
            [
                "SAE_LLM_BASE_URL=http://127.0.0.1:8000/v1",
                "SAE_LLM_MODEL=test-model",
                "SAE_LLM_TIMEOUT_SECONDS=45",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "brain.env").write_text(
        "\n".join(
            [
                "SAE_BRAIN_BASE_URL=https://brain.example.com/api",
                "SAE_BRAIN_SUBMIT_TIMEOUT_SECONDS=60",
                "SAE_BRAIN_POLL_INTERVAL_SECONDS=20",
                "SAE_BRAIN_MAX_POLLS=40",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    settings = load_runtime_settings(settings_dir=tmp_path, environ={})

    assert settings.environment == "development"
    assert settings.log_level == "DEBUG"
    assert settings.universe == "TOP1000"
    assert settings.llm is not None
    assert settings.llm.model == "test-model"
    assert settings.llm.timeout_seconds == 45.0
    assert settings.brain is not None
    assert settings.brain.max_polls == 40
    assert settings.loaded_env_files == ["default.env", "local.env", "llm.env", "brain.env"]


def test_process_environment_overrides_env_files(tmp_path):
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

    settings = load_runtime_settings(
        settings_dir=tmp_path,
        environ={"SAE_REGION": "KOR", "SAE_UNIVERSE": "TOP500"},
    )

    assert settings.region == "KOR"
    assert settings.universe == "TOP500"


def test_require_llm_raises_when_missing(tmp_path):
    (tmp_path / "default.env").write_text("SAE_ENV=development\n", encoding="utf-8")

    with pytest.raises(ValueError, match="LLM settings are required"):
        load_runtime_settings(settings_dir=tmp_path, environ={}, require_llm=True)


def test_partial_llm_configuration_is_rejected(tmp_path):
    (tmp_path / "default.env").write_text("SAE_ENV=development\n", encoding="utf-8")
    (tmp_path / "llm.env").write_text("SAE_LLM_BASE_URL=http://127.0.0.1:8000/v1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="LLM settings are partially configured"):
        load_runtime_settings(settings_dir=tmp_path, environ={})
