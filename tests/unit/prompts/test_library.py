from strategic_alpha_engine.prompts import (
    load_prompt_asset,
    load_prompt_golden_sample,
    list_prompt_assets,
    list_prompt_golden_samples,
    validate_prompt_golden_sample,
)


def test_list_prompt_assets_loads_all_roles():
    assets = list_prompt_assets()

    assert len(assets) == 4
    assert {asset.role for asset in assets} == {"agenda_generator", "planner", "blueprint", "critic"}


def test_planner_golden_sample_validates_against_contracts():
    sample = load_prompt_golden_sample("planner", "planner.quality_deterioration.001")

    validate_prompt_golden_sample(sample)


def test_all_golden_samples_validate_against_contracts():
    for sample in list_prompt_golden_samples():
        validate_prompt_golden_sample(sample)


def test_load_prompt_asset_returns_expected_sample_ids():
    asset = load_prompt_asset("critic")

    assert asset.prompt_id == "critic.default.v1"
    assert asset.sample_ids == ["critic.quality_deterioration.001"]
