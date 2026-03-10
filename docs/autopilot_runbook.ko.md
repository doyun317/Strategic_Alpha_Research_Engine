# Strategic Alpha Research Engine Autopilot Runbook

## 1. 목적

이 문서는 `autopilot` 실행 모드를 실제로 돌릴 때 필요한 최소 절차를 정리한다.

핵심 목표는 아래 두 가지다.

1. fake provider로 전체 autopilot 경로를 빠르게 smoke test 한다.
2. 실제 운영 전에는 WorldQuant + LLM 설정으로 제한된 live smoke를 다시 확인한다.

## 2. 사전 준비

- `settings/llm.env` 가 존재하고 `SAE_LLM_BASE_URL`, `SAE_LLM_MODEL` 이 유효하다.
- 실제 Brain smoke를 할 경우 `settings/brain.env` 가 존재하고 계정이 유효하다.
- `.venv` 와 개발 의존성이 준비되어 있다.

권장 시작 명령:

```bash
cd /workspace/Strategic_Alpha_Research_Engine
source .venv/bin/activate
```

## 3. fake provider smoke

새 artifact root를 잡고 fake Brain으로 끝까지 한 번 실행한다.

```bash
ART=/tmp/sae_autopilot_fake
rm -rf "$ART"

python -m strategic_alpha_engine autopilot \
  --artifacts-dir "$ART" \
  --brain-provider fake \
  --target-packet-count 2 \
  --packet-top-k 2 \
  --max-agendas 4 \
  --max-simulations 8 \
  --idle-rounds 2

python -m strategic_alpha_engine status --artifacts-dir "$ART"
```

확인 포인트:

- `autopilot` 출력에 `run_id`, `stopped_reason`, `packet_ids`, `packet_paths` 가 있다.
- `status.autopilot_status.ready_for_submission_packet_count > 0`
- `status.submission_packet_index.unique_signatures > 0`
- `status.latest_submission_manifest` 가 비어 있지 않다.

## 4. 실제 WorldQuant 제한 smoke

실제 외부 비용과 시간을 줄이기 위해 아주 작은 제한으로 확인한다.

```bash
ART=/tmp/sae_autopilot_real
rm -rf "$ART"

python -m strategic_alpha_engine config --require-llm --require-brain

python -m strategic_alpha_engine autopilot \
  --artifacts-dir "$ART" \
  --brain-provider worldquant \
  --target-packet-count 1 \
  --packet-top-k 1 \
  --max-agendas 1 \
  --max-simulations 1 \
  --idle-rounds 1

python -m strategic_alpha_engine status --artifacts-dir "$ART"
```

확인 포인트:

- 실제 submit / poll / fetch 가 성공한다.
- 결과가 packet까지 가지 않더라도 `stopped_reason` 과 run lineage가 기록된다.
- `state/latest_submission_manifest.json` 또는 `run_states.jsonl` 로 종료 상태를 해석할 수 있다.

## 5. 주요 산출물 경로

autopilot 실행 후 아래 파일들을 본다.

- `runs/<autopilot_run_id>/agenda_catalog.jsonl`
- `runs/<autopilot_run_id>/agenda_generation_summary.json`
- `runs/<autopilot_run_id>/autopilot_iterations.jsonl`
- `runs/<autopilot_run_id>/autopilot_manifest.json`
- `runs/<autopilot_run_id>/auto_review.jsonl`
- `state/submission_packet_index.jsonl`
- `state/latest_submission_manifest.json`

packet 자체는 기존 packet run 구조를 그대로 쓴다.

- `runs/<packet_run_id>/submission_packets.jsonl`
- `runs/<packet_run_id>/packets/<candidate_id>.json`

## 6. 운영 해석 기준

아래처럼 보면 된다.

- `target_packet_count_reached`: 목표 packet 수 달성
- `idle_round_limit_reached`: 최근 여러 round 동안 신규 packet 없음
- `max_agendas_reached`: agenda 탐색 상한 도달
- `max_simulations_reached`: simulation 상한 도달
- `agenda_generation_exhausted`: generator가 더 이상 신규 agenda를 만들지 못함

## 7. 주의사항

- `autopilot`은 실제 외부 제출을 하지 않는다.
- 기본 운영 경로는 `real LLM + real WorldQuant` 이지만, smoke test는 먼저 fake provider로 보는 게 안전하다.
- LLM endpoint가 느리면 `SAE_LLM_TIMEOUT_SECONDS` 를 늘려야 할 수 있다.
- Brain quota / 계정 상태에 따라 live smoke 결과는 달라질 수 있다.

## 8. 종료 후 확인

최종적으로 아래 두 파일만 열어도 제출 후보를 빠르게 볼 수 있어야 한다.

- `state/latest_submission_manifest.json`
- `runs/<packet_run_id>/submission_packets.jsonl`
