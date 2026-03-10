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
python -m strategic_alpha_engine prompt --role agenda_generator
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
python -m strategic_alpha_engine validate --artifacts-dir artifacts
python -m strategic_alpha_engine promote --artifacts-dir artifacts
python -m strategic_alpha_engine review --artifacts-dir artifacts --decision approve
python -m strategic_alpha_engine packet --artifacts-dir artifacts

# use the real WorldQuant Brain client instead of the fake adapter
# this requires settings/brain.env with SAE_BRAIN_BASE_URL, SAE_BRAIN_USERNAME, SAE_BRAIN_PASSWORD
python -m strategic_alpha_engine simulate --artifacts-dir artifacts --brain-provider worldquant

# optionally run a single explicit validation window instead of the default
# stage_b multi-period set: P1Y0M0D, P3Y0M0D, P5Y0M0D
python -m strategic_alpha_engine validate --artifacts-dir artifacts --period P3Y0M0D

# validate writes robust_promotion.jsonl and updates candidate stages,
# promote advances robust candidates into the submission-ready inventory and queue,
# review resolves pending human-review items,
# and packet materializes approved candidates into self-contained submission artifacts
# status now includes validation_summary, validation_matrix,
# robust_promotion_summary, submission_ready_inventory,
# human_review_queue, human_review_summary, and submission_packet_summary
python -m strategic_alpha_engine status --artifacts-dir artifacts

# optional: persist the status summary report
python -m strategic_alpha_engine status --artifacts-dir artifacts --out artifacts/reports/latest_status.json
```

Run the full autopilot alpha factory and emit a submission manifest:

```bash
# autopilot requires LLM settings, and worldquant mode also requires Brain settings
python -m strategic_alpha_engine autopilot --artifacts-dir artifacts --brain-provider fake

# production-style path: real LLM + real WorldQuant Brain
python -m strategic_alpha_engine autopilot --artifacts-dir artifacts --brain-provider worldquant

# inspect the latest manifest and cumulative packet index
python -m strategic_alpha_engine status --artifacts-dir artifacts
```

Inspect learner recommendations and optionally weight agendas:

```bash
python -m strategic_alpha_engine policy --artifacts-dir artifacts

# optionally pass multiple agenda payloads to get family-weighted priorities
python -m strategic_alpha_engine policy \
  --artifacts-dir artifacts \
  --agenda-in tmp/agenda_quality.json \
  --agenda-in tmp/agenda_momentum.json
```

Run a bounded research loop across prioritized agendas:

```bash
# without --agenda-in, the command uses the built-in sample agenda pool
python -m strategic_alpha_engine research-loop --artifacts-dir artifacts --iterations 2

# inspect queue state and latest loop recommendation snapshot
python -m strategic_alpha_engine status --artifacts-dir artifacts
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
- prompt assets and golden samples for agenda_generator / planner / blueprint / critic roles
- standalone `plan`, `synthesize`, `simulate`, and `status` CLI workflows
- immutable simulation request / run domain models
- Brain simulation client contract and fake adapter
- simulation orchestrator workflow for critique-passed candidates
- Stage A evaluation records and rule-based promotion decisions after simulation
- ValidationRecord domain, validation artifacts, and standalone `validate` CLI
- multi-period validation runner with latest validation matrix summary in `status`
- robust candidate promotion after validation, including diversity guard and `robust_promotion.jsonl`
- submission-ready promotion workflow and `promote` CLI
- submission-ready artifact/state ledgers with inventory summary in `status`
- pending human review queue created from promote runs
- `review` CLI with approve / hold / reject decisions and human review ledgers
- `packet` CLI with self-contained submission packet artifacts for approved candidates
- `autopilot` CLI for agenda generation through packet + latest submission manifest
- OpenAI-compatible structured LLM client with schema/empty-response retry policy
- hybrid agenda generation with template seeding and LLM augmentation
- autopilot submission packet index and latest submission manifest in local state
- local file-based artifact ledger for run outputs
- local manifest-based state ledger for candidate/run/family state and status summaries
- optional real WorldQuant Brain simulation client behind `--brain-provider worldquant`
- local agenda queue ledger and bounded `research-loop` execution mode
- artifact persistence for `evaluations.jsonl`, `promotion.jsonl`, and `robust_promotion.jsonl`
- validation backlog tracking and validation summary in `status`
- learner-ready family stats and `family_learner_summaries.json`
- heuristic family policy recommendations and agenda weighting via `policy`
- static planner and blueprint builder
- skeleton-based candidate synthesizer
- rule-based strategic critic
- `research-once` workflow scaffold

Automatic external submission and review UI are still intentionally left out of scope.
