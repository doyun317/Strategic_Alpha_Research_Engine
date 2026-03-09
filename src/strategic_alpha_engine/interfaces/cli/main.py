from __future__ import annotations

import argparse
import json
from pathlib import Path

from strategic_alpha_engine.application.services import (
    MetadataBackedStaticValidator,
    RuleBasedStrategicCritic,
    SkeletonCandidateSynthesizer,
    StaticBlueprintBuilder,
    StaticHypothesisPlanner,
)
from strategic_alpha_engine.application.workflows import ResearchOnceWorkflow
from strategic_alpha_engine.config import load_runtime_settings
from strategic_alpha_engine.domain import (
    CritiqueReport,
    ExpressionCandidate,
    HypothesisSpec,
    SignalBlueprint,
    ResearchAgenda,
    StaticValidationReport,
    build_sample_critique_report,
    build_sample_expression_candidate,
    build_sample_hypothesis_spec,
    build_sample_research_agenda,
    build_sample_signal_blueprint,
)
from strategic_alpha_engine.domain.enums import FieldClass, ResearchHorizon
from strategic_alpha_engine.infrastructure.metadata import load_seed_metadata_catalog
from strategic_alpha_engine.prompts import load_prompt_asset, load_prompt_golden_sample


def _write_output(payload: dict | list, output_path: str | None) -> None:
    rendered = json.dumps(payload, indent=2)
    if not output_path:
        print(rendered)
        return
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Strategic Alpha Engine developer CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    schema_parser = subparsers.add_parser("schema", help="Print JSON schema for a model")
    schema_parser.add_argument(
        "--model",
        choices=["agenda", "hypothesis", "blueprint", "candidate", "critique", "static_validation"],
        required=True,
    )
    schema_parser.add_argument("--out", default=None)

    example_parser = subparsers.add_parser("example", help="Print example payload for a model")
    example_parser.add_argument(
        "--model",
        choices=["agenda", "hypothesis", "blueprint", "candidate", "critique", "static_validation"],
        required=True,
    )
    example_parser.add_argument("--out", default=None)

    research_once_parser = subparsers.add_parser(
        "research-once",
        help="Run the static structured-generation workflow once and print the result",
    )
    research_once_parser.add_argument("--out", default=None)

    config_parser = subparsers.add_parser("config", help="Load and print runtime settings")
    config_parser.add_argument("--settings-dir", default=None)
    config_parser.add_argument("--require-llm", action="store_true")
    config_parser.add_argument("--require-brain", action="store_true")
    config_parser.add_argument("--out", default=None)

    catalog_parser = subparsers.add_parser("catalog", help="Inspect seeded metadata catalog")
    catalog_parser.add_argument("--view", choices=["summary", "fields", "operators"], default="summary")
    catalog_parser.add_argument("--field-class", choices=[field_class.value for field_class in FieldClass])
    catalog_parser.add_argument("--horizon", choices=[horizon.value for horizon in ResearchHorizon])
    catalog_parser.add_argument("--limit", type=int, default=10)
    catalog_parser.add_argument("--out", default=None)

    prompt_parser = subparsers.add_parser("prompt", help="Inspect prompt assets and golden samples")
    prompt_parser.add_argument("--role", choices=["planner", "blueprint", "critic"], required=True)
    prompt_parser.add_argument("--sample-id", default=None)
    prompt_parser.add_argument("--out", default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "schema":
        schema_map = {
            "agenda": ResearchAgenda.model_json_schema(),
            "hypothesis": HypothesisSpec.model_json_schema(),
            "blueprint": SignalBlueprint.model_json_schema(),
            "candidate": ExpressionCandidate.model_json_schema(),
            "critique": CritiqueReport.model_json_schema(),
            "static_validation": StaticValidationReport.model_json_schema(),
        }
        payload = schema_map[args.model]
        _write_output(payload, args.out)
        return 0

    if args.command == "example":
        example_map = {
            "agenda": build_sample_research_agenda().model_dump(),
            "hypothesis": build_sample_hypothesis_spec().model_dump(),
            "blueprint": build_sample_signal_blueprint().model_dump(),
            "candidate": build_sample_expression_candidate().model_dump(),
            "critique": build_sample_critique_report().model_dump(),
            "static_validation": MetadataBackedStaticValidator(
                load_seed_metadata_catalog()
            ).validate(
                build_sample_signal_blueprint(),
                build_sample_expression_candidate(),
            ).model_dump(),
        }
        payload = example_map[args.model]
        _write_output(payload, args.out)
        return 0

    if args.command == "research-once":
        workflow = ResearchOnceWorkflow(
            hypothesis_planner=StaticHypothesisPlanner(),
            blueprint_builder=StaticBlueprintBuilder(),
            candidate_synthesizer=SkeletonCandidateSynthesizer(),
            static_validator=MetadataBackedStaticValidator(load_seed_metadata_catalog()),
            strategic_critic=RuleBasedStrategicCritic(),
        )
        result = workflow.run(build_sample_research_agenda())
        payload = result.model_dump()
        _write_output(payload, args.out)
        return 0

    if args.command == "config":
        try:
            settings = load_runtime_settings(
                settings_dir=args.settings_dir,
                require_llm=args.require_llm,
                require_brain=args.require_brain,
            )
        except ValueError as exc:
            parser.exit(status=2, message=f"{exc}\n")
        payload = settings.model_dump(mode="json")
        _write_output(payload, args.out)
        return 0

    if args.command == "catalog":
        catalog = load_seed_metadata_catalog()
        if args.view == "summary":
            payload = {
                "field_count": len(catalog.fields),
                "operator_count": len(catalog.operators),
                "field_ids": [field.field_id for field in catalog.fields],
                "operator_ids": [operator.operator_id for operator in catalog.operators],
            }
        elif args.view == "fields":
            field_classes = [args.field_class] if args.field_class else None
            horizons = [args.horizon] if args.horizon else None
            payload = [
                entry.model_dump(mode="json")
                for entry in catalog.build_field_excerpt(
                    field_classes=field_classes,
                    horizons=horizons,
                    limit=args.limit,
                )
            ]
        else:
            payload = [
                operator.model_dump(mode="json")
                for operator in catalog.operators[: args.limit]
            ]
        _write_output(payload, args.out)
        return 0

    if args.command == "prompt":
        if args.sample_id:
            payload = load_prompt_golden_sample(args.role, args.sample_id).model_dump(mode="json")
        else:
            payload = load_prompt_asset(args.role).model_dump(mode="json")
        _write_output(payload, args.out)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 1
