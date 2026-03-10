from strategic_alpha_engine.application.contracts import BlueprintBuilderPromptOutput


def test_blueprint_prompt_output_repairs_forbidden_lookbacks_and_slot_names():
    payload = {
        "blueprint": {
            "blueprint_id": "bp.test.001",
            "hypothesis_id": "hyp.test.001",
            "summary": "Blueprint summary long enough for validation.",
            "expression_intent": "Create a conservative ranked cross-sectional signal.",
            "field_selections": [
                {
                    "field_id": "close",
                    "field_class": "price",
                    "update_cadence": "daily",
                    "role": "primary_signal",
                    "rationale": "Primary price field for the thesis.",
                },
                {
                    "field_id": "volume",
                    "field_class": "liquidity",
                    "update_cadence": "daily",
                    "role": "secondary_signal",
                    "rationale": "Liquidity confirmation field for the thesis.",
                },
            ],
            "primary_fields": ["close", "volume"],
            "secondary_fields": [],
            "transform_plan": [
                {
                    "name": "price_zscore",
                    "kind": "zscore",
                    "input_fields": ["close"],
                    "lookback_days": 20,
                    "rationale": "Normalize price cross-sectionally.",
                },
                {
                    "name": "volume_zscore",
                    "kind": "zscore",
                    "input_fields": ["volume"],
                    "lookback_days": 10,
                    "rationale": "Normalize volume cross-sectionally.",
                },
            ],
            "normalization_plan": [
                {
                    "kind": "cross_sectional_rank",
                    "target": "final_expression",
                    "rationale": "Final output must be ranked cross-sectionally.",
                }
            ],
            "risk_control_plan": [],
            "operator_policy": {
                "allowed_operators": ["rank", "subtract"],
                "forbidden_operators": ["trade_when"],
                "max_operator_count": 4,
                "max_nesting_depth": 3,
                "require_explicit_lookbacks": True,
                "require_outer_normalization": True,
            },
            "skeleton_templates": [
                {
                    "template_id": "skeleton.rank_spread.001",
                    "name": "Ranked spread skeleton",
                    "template": "rank(zscore(close) - zscore(volume))",
                    "slot_names": ["FIELD_A", "FIELD_B"],
                    "rationale": "Use ranked spread between price and volume.",
                }
            ],
            "disallowed_patterns": ["missing_outer_rank"],
            "target_expression_count": 4,
            "notes": "LLM output may need deterministic repair.",
        },
        "design_notes": ["Repairable payload"],
    }

    result = BlueprintBuilderPromptOutput.model_validate(payload)

    assert result.blueprint.transform_plan[0].lookback_days is None
    assert result.blueprint.transform_plan[1].lookback_days is None
    assert result.blueprint.skeleton_templates[0].slot_names == ["FIELD_A", "FIELD_B"]
    assert result.blueprint.skeleton_templates[0].template == "rank(zscore(FIELD_A) - zscore(FIELD_B))"
