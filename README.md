# Strategic Alpha Research Engine

Greenfield scaffold for a strategic alpha research system built around:

- `Research Agenda -> Hypothesis Spec -> Signal Blueprint -> Expression Candidates`
- structured validation and critique before simulation
- explicit artifact lineage instead of expression-only generation

Current status:
- architecture spec exists
- MVP scope doc exists
- repository scaffold exists
- `HypothesisSpec` and `SignalBlueprint` are implemented as validated Pydantic schemas
- Phase 1 structured-generation foundation exists
- `research-once` static workflow is available

## Documents

- Greenfield target architecture:
  - [docs/target_greenfield_alpha_research_architecture.ko.md](./docs/target_greenfield_alpha_research_architecture.ko.md)
- MVP scope:
  - [docs/mvp_scope.ko.md](./docs/mvp_scope.ko.md)
- Phase 1 scope:
  - [docs/phase1_structured_generation_foundation.ko.md](./docs/phase1_structured_generation_foundation.ko.md)
- Phase 3 scope:
  - [docs/phase3_learning_loop.ko.md](./docs/phase3_learning_loop.ko.md)
- Phase 4 scope:
  - [docs/phase4_robust_validation.ko.md](./docs/phase4_robust_validation.ko.md)
- Phase 5 scope:
  - [docs/phase5_submission_prep_layer.ko.md](./docs/phase5_submission_prep_layer.ko.md)

## Quickstart

```bash
cd /workspace/Strategic_Alpha_Research_Engine
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
```

## Local Environment Files

Tracked templates:

- `settings/default.env`: shareable defaults
- `settings/local.env.example`: local non-secret overrides template
- `settings/llm.env.example`: local LLM configuration template
- `settings/brain.env.example`: local Brain/runtime integration template

Ignored runtime files:

- `settings/local.env`
- `settings/llm.env`
- `settings/brain.env`

Create local copies before adding private values:

```bash
cp settings/local.env.example settings/local.env
cp settings/llm.env.example settings/llm.env
cp settings/brain.env.example settings/brain.env
```

Inspect resolved runtime settings:

```bash
python -m strategic_alpha_engine config
python -m strategic_alpha_engine config --require-llm
```

Inspect seeded metadata catalog:

```bash
python -m strategic_alpha_engine catalog --view summary
python -m strategic_alpha_engine catalog --view fields --field-class fundamental --horizon medium
python -m strategic_alpha_engine catalog --view operators
```

Inspect prompt assets and golden samples:

```bash
python -m strategic_alpha_engine prompt --role planner
python -m strategic_alpha_engine prompt --role critic --sample-id critic.quality_deterioration.001
```

Run planning and synthesis separately:

```bash
python -m strategic_alpha_engine plan
python -m strategic_alpha_engine synthesize

# or persist intermediate JSON locally
python -m strategic_alpha_engine plan --out tmp/plan.json
python -m strategic_alpha_engine synthesize --plan-in tmp/plan.json --out tmp/synthesis.json
```

Run simulation and inspect local status:

```bash
# current simulate command uses the fake Brain adapter, evaluates Stage A,
# and persists local ledgers plus evaluation/promotion artifacts
python -m strategic_alpha_engine simulate --artifacts-dir artifacts
python -m strategic_alpha_engine status --artifacts-dir artifacts

# optional: persist the status summary report
python -m strategic_alpha_engine status --artifacts-dir artifacts --out artifacts/reports/latest_status.json
```

## Schema Commands

Print JSON schema:

```bash
python -m strategic_alpha_engine schema --model hypothesis
python -m strategic_alpha_engine schema --model blueprint
```

Print example payload:

```bash
python -m strategic_alpha_engine example --model hypothesis
python -m strategic_alpha_engine example --model blueprint
python -m strategic_alpha_engine example --model agenda
```

Run one static research workflow:

```bash
python -m strategic_alpha_engine research-once
```

## Current Package Layout

```text
src/strategic_alpha_engine/
  application/
  config/
  domain/
  infrastructure/
  interfaces/
  prompts/
```

Current implementation includes:
- domain schemas for agenda, hypothesis, blueprint, candidate, critique
- metadata-backed static validator before critique
- prompt assets and golden samples for planner / blueprint / critic roles
- standalone `plan`, `synthesize`, `simulate`, and `status` CLI workflows
- immutable simulation request / run domain models
- Brain simulation client contract and fake adapter
- simulation orchestrator workflow for critique-passed candidates
- Stage A evaluation records and rule-based promotion decisions after simulation
- local file-based artifact ledger for run outputs
- local manifest-based state ledger for candidate/run/family state and status summaries
- artifact persistence for `evaluations.jsonl` and `promotion.jsonl`
- learner-ready family stats and `family_learner_summaries.json`
- static planner and blueprint builder
- skeleton-based candidate synthesizer
- rule-based strategic critic
- `research-once` workflow scaffold

Brain/vLLM adapters, persistent repositories, and real research loops are still intentionally left for the next phase.
