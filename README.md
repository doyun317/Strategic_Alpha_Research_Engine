# Strategic Alpha Research Engine

Autopilot-first alpha research system built around:

- `ResearchAgenda -> HypothesisSpec -> SignalBlueprint -> ExpressionCandidate`
- structured LLM generation with metadata-aware validation
- WorldQuant Brain simulation orchestration
- local artifact/state ledgers with submission packet lineage
- `autopilot` as the single operational runtime entrypoint

Current status:

- Phase 1 through Phase 6 implementation is complete
- runtime usage is now `autopilot`-centric
- earlier standalone entrypoints were retired from the public CLI surface
- internal planning / synthesis / simulation / validation / promotion / review / packet workflows remain as shared engine components used by `autopilot`

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
- Phase 6 scope:
  - [docs/phase6_autopilot_alpha_factory.ko.md](./docs/phase6_autopilot_alpha_factory.ko.md)
- Phase 2~6 incremental roadmap:
  - [docs/phase2_incremental_delivery_plan.ko.md](./docs/phase2_incremental_delivery_plan.ko.md)
- Operational readiness checklist:
  - [docs/operational_readiness_checklist.ko.md](./docs/operational_readiness_checklist.ko.md)
- Submission packet runbook:
  - [docs/submission_packet_runbook.ko.md](./docs/submission_packet_runbook.ko.md)
- Autopilot runbook:
  - [docs/autopilot_runbook.ko.md](./docs/autopilot_runbook.ko.md)

## Quickstart

```bash
cd /workspace/Strategic_Alpha_Research_Engine
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
./.venv/bin/pytest -q
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
python -m strategic_alpha_engine config --require-brain
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
python -m strategic_alpha_engine prompt --role agenda_generator
```

Run the autopilot alpha factory:

```bash
ART=artifacts

# fake provider smoke
python -m strategic_alpha_engine autopilot --artifacts-dir "$ART" --brain-provider fake
```

Production-style run:

```bash
python -m strategic_alpha_engine autopilot --artifacts-dir "$ART" --brain-provider worldquant
```

Inspect runtime outputs:

```bash
python -m strategic_alpha_engine status --artifacts-dir "$ART"
cat "$ART/state/latest_submission_manifest.json"
```

## Developer Commands

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
- prompt assets and golden samples for agenda_generator / planner / blueprint / critic roles
- immutable simulation request / run domain models
- Brain simulation client contract, fake adapter, and optional WorldQuant adapter
- simulation orchestration for critique-passed candidates
- Stage A evaluation records and rule-based promotion decisions after simulation
- ValidationRecord domain, validation artifacts, and multi-period validation runner
- robust candidate promotion, submission-ready ledgers, and human review artifacts
- submission packet generation with cumulative packet index and latest submission manifest
- `autopilot` CLI for agenda generation through packet + manifest
- OpenAI-compatible structured LLM client with schema/empty-response retry policy
- hybrid agenda generation with template seeding and LLM augmentation
- local file-based artifact ledger for run outputs
- local manifest-based state ledger for candidate/run/family state and status summaries
- learner-ready family stats and family weighting used by agenda generation
- skeleton-based candidate synthesizer
- structured LLM-backed planner / blueprint builder / critic

Automatic external submission and review UI are still intentionally left out of scope.
