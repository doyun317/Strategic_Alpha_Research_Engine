# Strategic Alpha Research Engine 운영 전 점검 체크리스트

## 1. 목적

이 문서는 현재 운영 경로인 `autopilot -> status -> latest_submission_manifest.json`
흐름을 다시 실행하면서 무엇을 확인해야 하는지 정리한 체크리스트다.

핵심 목표는 아래 네 가지다.

1. 회귀 테스트를 빠뜨리지 않는다.
2. `autopilot` fake smoke를 다시 재현한다.
3. 필요 시 제한된 WorldQuant live smoke를 다시 확인한다.
4. artifact, state, manifest, packet lineage가 실제로 일관적인지 본다.

## 2. 사전 준비

- [ ] `/workspace/Strategic_Alpha_Research_Engine` 기준으로 작업한다.
- [ ] `.venv`가 준비되어 있다.
- [ ] 개발 의존성이 설치되어 있다.
- [ ] `settings/default.env`, `settings/local.env`, `settings/llm.env`, `settings/brain.env` 구성이 현재 목적에 맞다.
- [ ] 테스트용 artifact 디렉터리를 새로 잡는다. 예: `/tmp/sae_autopilot_check`

권장 시작 명령:

```bash
cd /workspace/Strategic_Alpha_Research_Engine
source .venv/bin/activate
rm -rf /tmp/sae_autopilot_check /tmp/sae_autopilot_check_real
```

## 3. 설정 점검

- [ ] `python -m strategic_alpha_engine config` 가 정상 종료한다.
- [ ] 출력된 `region`, `universe`, `default_test_period`가 의도와 맞다.
- [ ] `python -m strategic_alpha_engine config --require-llm` 가 정상 종료한다.
- [ ] 실제 Brain을 쓸 계획이면 `python -m strategic_alpha_engine config --require-brain` 가 정상 종료한다.
- [ ] `settings/llm.env` 가 structured JSON 응답을 줄 수 있는 endpoint를 가리킨다.
- [ ] 실제 live smoke 전에는 `settings/brain.env` 의 `base_url`, `username`, `password`가 현재 계정 기준으로 맞다.

## 4. 회귀 테스트

- [ ] 전체 테스트를 실행한다.

```bash
./.venv/bin/pytest -q
```

- [ ] 실패한 테스트가 없다.
- [ ] 새로 실패한 테스트가 있으면 먼저 수정하고 smoke test로 넘어간다.

## 5. 메타데이터 / 프롬프트 점검

- [ ] catalog 조회가 정상 동작한다.
- [ ] prompt asset과 golden sample 로딩이 정상 동작한다.

```bash
python -m strategic_alpha_engine catalog --view summary
python -m strategic_alpha_engine prompt --role planner
python -m strategic_alpha_engine prompt --role critic --sample-id critic.quality_deterioration.001
python -m strategic_alpha_engine prompt --role agenda_generator
```

## 6. Autopilot fake smoke

아래 순서대로 새 artifact 디렉터리에서 fake provider smoke를 실행한다.

```bash
ART=/tmp/sae_autopilot_check
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

확인 항목:

- [ ] `autopilot` 출력에 `run_id`, `stopped_reason`, `packet_ids`, `latest_submission_manifest`가 있다.
- [ ] `status.autopilot_status.current_state` 가 `idle` 또는 `failed` 로 해석 가능하다.
- [ ] `status.autopilot_status.latest_submission_manifest_path` 가 비어 있지 않다.
- [ ] `status.submission_packet_index.unique_signatures > 0`
- [ ] `status.latest_submission_manifest.selected_packet_count > 0`

## 7. 제한된 WorldQuant live smoke

실제 외부 비용과 시간을 줄이기 위해 작은 제한으로 한 번만 확인한다.

```bash
ART=/tmp/sae_autopilot_check_real
rm -rf "$ART"

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

확인 항목:

- [ ] 실제 submit / poll / fetch 가 성공하거나, 실패 시 원인이 `run_states.jsonl`에 남는다.
- [ ] packet까지 가지 않더라도 `stopped_reason` 과 run lineage가 기록된다.
- [ ] `state/latest_submission_manifest.json` 또는 `run_states.jsonl` 로 종료 상태를 해석할 수 있다.

## 8. status 확인 포인트

`status` 결과에서 아래를 본다.

- [ ] `autopilot_status.latest_run_id` 가 있다.
- [ ] `autopilot_status.latest_submission_manifest_path` 가 있다.
- [ ] `submission_packet_index.unique_signatures >= latest_submission_manifest.selected_packet_count`
- [ ] `latest_submission_manifest.selected_packet_count >= 0`
- [ ] `candidate_stage_counts` 값이 다른 요약과 충돌하지 않는다.
- [ ] `family_stats` 와 `family_learner_summaries` 의 family별 수치가 상식적으로 맞다.

추가 확인:

- [ ] `runs.counts_by_kind.autopilot >= 1`
- [ ] internal subrun들이 남는 경우 simulation / validation / promotion / review / packet count가 모두 같은 umbrella run lineage 안에서 해석 가능하다.

## 9. artifact 확인 포인트

아래 파일이 실제로 생성되었는지 확인한다.

- [ ] `runs/<autopilot_run_id>/agenda_catalog.jsonl`
- [ ] `runs/<autopilot_run_id>/agenda_generation_summary.json`
- [ ] `runs/<autopilot_run_id>/autopilot_iterations.jsonl`
- [ ] `runs/<autopilot_run_id>/autopilot_manifest.json`
- [ ] `runs/<autopilot_run_id>/auto_review.jsonl`
- [ ] `runs/<packet_run_id>/submission_packets.jsonl`
- [ ] `runs/<packet_run_id>/packets/<candidate_id>.json`

추가 확인:

- [ ] packet JSON 하나를 열었을 때 `agenda`, `hypothesis`, `blueprint`, `candidate_artifact`, `simulation_artifact`, `validation_summary`, `review_decision`이 모두 들어 있다.
- [ ] packet 안의 `candidate_id`가 nested artifact 전반에서 일치한다.
- [ ] manifest의 `packet_paths`와 실제 packet 파일이 일치한다.

## 10. 상태 ledger 확인 포인트

`artifacts/state` 아래에서 아래를 확인한다.

- [ ] `candidate_stages.jsonl`
- [ ] `run_states.jsonl`
- [ ] `family_stats.json`
- [ ] `family_learner_summaries.json`
- [ ] `validation_backlog.jsonl`
- [ ] `submission_packet_index.jsonl`
- [ ] `latest_submission_manifest.json`

추가 확인:

- [ ] 같은 candidate가 stage를 거치면서 최신 상태 하나로 해석 가능하다.
- [ ] `run_states.jsonl` 에서 umbrella autopilot run과 subrun의 `parent_run_id` 관계를 따라갈 수 있다.
- [ ] `validation_backlog`가 append-only여도 latest 상태 기준으로 읽으면 일관된다.

## 11. 현재 구현의 한계

아래는 실패가 아니라 현재 설계상 전제다.

- [ ] 기본 smoke test는 fake Brain adapter 기준이다.
- [ ] `autopilot` 은 LLM endpoint 의 응답 시간과 schema 준수에 의존한다.
- [ ] 실제 외부 API 연동은 `autopilot --brain-provider worldquant` 로 별도 검증해야 한다.
- [ ] packet에는 lineage와 rationale이 들어가므로 외부 공유 전에 민감도 검토가 필요하다.
- [ ] 실제 외부 제출 자동화는 아직 구현되지 않았다.

## 12. Go / No-Go 기준

배포 전 또는 다음 구현 단계로 넘어가기 전 아래를 만족하면 `Go`다.

- [ ] `pytest -q` 전체 통과
- [ ] fake autopilot smoke 성공
- [ ] 필요 시 제한된 WorldQuant live smoke 성공 또는 실패 원인 명확
- [ ] status 요약 간 수치 충돌 없음
- [ ] artifact와 state 파일 생성 확인
- [ ] packet lineage 검토 완료
- [ ] autopilot manifest와 packet index 검토 완료

아래 중 하나라도 해당하면 `No-Go`다.

- [ ] 같은 candidate의 lineage가 artifact마다 다르다.
- [ ] stage count와 inventory summary가 서로 맞지 않는다.
- [ ] manifest가 생성되었는데 packet 파일과 내용이 맞지 않는다.
- [ ] packet이 self-contained하지 않다.
- [ ] 테스트는 통과하지만 smoke에서 실제 파일이 생성되지 않는다.

## 13. 권장 기록

점검 후 아래만 간단히 남겨두면 된다.

- 점검 일시:
- 점검 브랜치:
- `pytest -q` 결과:
- fake smoke artifact root:
- live smoke artifact root:
- 최종 판단: `Go` / `No-Go`
