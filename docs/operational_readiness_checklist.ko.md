# Strategic Alpha Research Engine 운영 전 점검 체크리스트

## 1. 목적

이 문서는 현재 구현된 Phase 1~6 범위를 실제로 다시 실행하면서
무엇을 테스트해야 하고 무엇을 확인해야 하는지 빠르게 점검하기 위한 체크리스트다.

이 문서의 목표는 네 가지다.

1. 회귀 테스트를 빠뜨리지 않는다.
2. `simulate -> validate -> promote -> review -> packet -> status` 전체 흐름을 재현한다.
3. `autopilot -> status` 자동화 경로를 재현한다.
4. artifact, state, lineage가 실제로 일관적인지 확인한다.

## 2. 사전 준비

- [ ] `/workspace/Strategic_Alpha_Research_Engine` 기준으로 작업한다.
- [ ] `.venv`가 준비되어 있다.
- [ ] 개발 의존성이 설치되어 있다.
- [ ] `settings/default.env`, `settings/local.env`, `settings/llm.env`, `settings/brain.env` 구성이 현재 목적에 맞다.
- [ ] 테스트용 artifact 디렉터리를 새로 잡는다. 예: `/tmp/sae_check`

권장 시작 명령:

```bash
cd /workspace/Strategic_Alpha_Research_Engine
source .venv/bin/activate
rm -rf /tmp/sae_check /tmp/sae_autopilot_check
```

## 3. 설정 점검

- [ ] `python -m strategic_alpha_engine config` 가 정상 종료한다.
- [ ] 출력된 `region`, `universe`, `default_test_period`가 의도와 맞다.
- [ ] LLM 설정이 필요한 경우 `python -m strategic_alpha_engine config --require-llm` 가 정상 종료한다.
- [ ] Brain 설정을 실제로 쓸 계획이면 `python -m strategic_alpha_engine config --require-brain` 가 정상 종료한다.
- [ ] 실제 WorldQuant Brain 연동을 검증할 계획이면 `settings/brain.env` 의 `base_url`, `username`, `password`가 현재 계정 기준으로 맞다.
- [ ] `autopilot` 를 쓸 계획이면 `settings/llm.env` 가 실제 structured JSON 응답을 줄 수 있는 endpoint를 가리킨다.

## 4. 회귀 테스트

- [ ] 전체 테스트를 실행한다.

```bash
./.venv/bin/pytest -q
```

- [ ] 실패한 테스트가 없다.
- [ ] 새로 실패한 테스트가 있다면 먼저 원인을 수정하고 그 다음 smoke test로 넘어간다.

## 5. 메타데이터 / 프롬프트 점검

- [ ] catalog 조회가 정상 동작한다.
- [ ] prompt asset과 golden sample 로딩이 정상 동작한다.

```bash
python -m strategic_alpha_engine catalog --view summary
python -m strategic_alpha_engine prompt --role planner
python -m strategic_alpha_engine prompt --role critic --sample-id critic.quality_deterioration.001
python -m strategic_alpha_engine prompt --role agenda_generator
```

## 6. 전체 파이프라인 smoke test

아래 순서대로 새 artifact 디렉터리에서 한 번 끝까지 실행한다.

```bash
ART=/tmp/sae_check

python -m strategic_alpha_engine simulate --artifacts-dir "$ART"
python -m strategic_alpha_engine validate --artifacts-dir "$ART"
python -m strategic_alpha_engine promote --artifacts-dir "$ART"
python -m strategic_alpha_engine review --artifacts-dir "$ART" --decision approve
python -m strategic_alpha_engine packet --artifacts-dir "$ART"
python -m strategic_alpha_engine status --artifacts-dir "$ART"
```

실제 WorldQuant Brain으로 시뮬레이션까지 확인하려면 별도로 아래를 실행한다.

```bash
ART=/tmp/sae_check_real
python -m strategic_alpha_engine simulate --artifacts-dir "$ART" --brain-provider worldquant
```

확인 항목:

- [ ] `simulate` 가 `run_id`, `accepted_candidate_ids`, `simulated_candidate_ids`, `promoted_candidate_ids`를 출력한다.
- [ ] `validate` 가 `validation_summary`, `validation_matrix`, `robust_promoted_candidate_ids`를 출력한다.
- [ ] `promote` 가 `submission_ready_candidate_ids`와 `queued_review_candidate_ids`를 출력한다.
- [ ] `review` 가 `approved_candidate_ids` 또는 의도한 decision 결과를 출력한다.
- [ ] `packet` 이 `packet_ids`와 `submission_packet_summary`를 출력한다.
- [ ] `status` 가 전체 상태 요약을 JSON으로 출력한다.

## 7. Autopilot smoke test

fake provider 기준 전체 autopilot 경로를 다시 확인한다.

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

- [ ] `autopilot` 출력에 `packet_ids` 와 `latest_submission_manifest` 가 들어 있다.
- [ ] `status.autopilot_status.current_state` 가 `idle` 또는 `failed` 로 해석 가능하다.
- [ ] `status.autopilot_status.latest_submission_manifest_path` 가 비어 있지 않다.
- [ ] `status.submission_packet_index.unique_signatures > 0`
- [ ] `status.latest_submission_manifest.selected_packet_count > 0`

실제 WorldQuant smoke가 필요하면 아래를 별도로 실행한다.

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
```

## 8. status 확인 포인트

`status` 결과에서 아래를 본다.

- [ ] `validation_summary.total_records > 0`
- [ ] `validation_matrix.total_candidates > 0`
- [ ] `robust_promotion_summary.total_decisions > 0`
- [ ] `submission_ready_inventory.total_candidates > 0`
- [ ] `human_review_queue.total_entries > 0`
- [ ] `human_review_summary.total_decisions > 0`
- [ ] `submission_packet_summary.total_packets > 0`
- [ ] `autopilot_status.latest_run_id` 가 있거나 manual-only artifact root라면 `None` 이다.
- [ ] `submission_packet_index.unique_signatures >= submission_packet_summary.total_packets`
- [ ] `latest_submission_manifest.selected_packet_count >= 0`
- [ ] `runs.counts_by_kind.simulate == 1`
- [ ] `runs.counts_by_kind.validate == 1`
- [ ] `runs.counts_by_kind.promote == 1`
- [ ] `runs.counts_by_kind.review == 1`
- [ ] `runs.counts_by_kind.packet == 1`

추가 확인:

- [ ] `agenda_status.latest_run_kind` 가 마지막 실행 명령과 맞다.
- [ ] `candidate_stage_counts` 값이 `status`의 다른 요약과 충돌하지 않는다.
- [ ] `family_stats` 와 `family_learner_summaries` 의 family별 수치가 상식적으로 맞다.

## 9. artifact 확인 포인트

아래 파일이 실제로 생성되었는지 확인한다.

- [ ] `runs/<simulate_run_id>/candidates.jsonl`
- [ ] `runs/<simulate_run_id>/simulations.jsonl`
- [ ] `runs/<simulate_run_id>/evaluations.jsonl`
- [ ] `runs/<validate_run_id>/validations.jsonl`
- [ ] `runs/<validate_run_id>/validation_matrix.json`
- [ ] `runs/<validate_run_id>/robust_promotion.jsonl`
- [ ] `runs/<promote_run_id>/submission_ready.jsonl`
- [ ] `runs/<review_run_id>/human_review.jsonl`
- [ ] `runs/<review_run_id>/review_queue.jsonl`
- [ ] `runs/<packet_run_id>/submission_packets.jsonl`
- [ ] `runs/<packet_run_id>/packets/<candidate_id>.json`
- [ ] `runs/<autopilot_run_id>/agenda_catalog.jsonl`
- [ ] `runs/<autopilot_run_id>/autopilot_iterations.jsonl`
- [ ] `runs/<autopilot_run_id>/autopilot_manifest.json`
- [ ] `runs/<autopilot_run_id>/auto_review.jsonl`

추가 확인:

- [ ] packet JSON 하나를 열었을 때 `agenda`, `hypothesis`, `blueprint`, `candidate_artifact`, `simulation_artifact`, `validation_summary`, `review_decision`이 모두 들어 있다.
- [ ] packet 안의 `candidate_id`가 nested artifact 전반에서 일치한다.
- [ ] validation summary의 `validation_ids`와 원본 validation record가 일치한다.

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
- [ ] `run_states.jsonl` 에서 각 run이 `started -> completed` 또는 `started -> failed` 형태로 남는다.
- [ ] `validation_backlog`가 append-only여도 latest 상태 기준으로 읽으면 일관된다.

## 11. 예외 시나리오 테스트

아래는 최소 한 번씩 확인하는 것이 좋다.

### 11.1 Human review hold

- [ ] `review --decision hold` 를 실행해 본다.
- [ ] 해당 candidate가 `submission_ready_inventory`에서 빠지거나 상태상 `robust_candidate`로 해석되는지 확인한다.
- [ ] `human_review_queue.counts_by_status.held` 가 올라가는지 확인한다.

### 11.2 Human review reject

- [ ] `review --decision reject` 를 실행해 본다.
- [ ] 해당 candidate가 최종적으로 `rejected` stage로 해석되는지 확인한다.

### 11.3 Single-period validation

- [ ] `validate --period P3Y0M0D` 를 실행해 본다.
- [ ] `validation_matrix.required_passing_periods == 1` 인지 확인한다.

### 11.4 Candidate-specific packet

- [ ] `packet --candidate-id <candidate_id>` 로 특정 candidate만 packet 생성해 본다.
- [ ] 생성된 packet 수가 정확히 1개인지 확인한다.

## 12. Research loop / learner 점검

Phase 3 기능도 같이 점검하려면 아래를 추가 실행한다.

```bash
ART=/tmp/sae_check_loop
rm -rf "$ART"

python -m strategic_alpha_engine research-loop --artifacts-dir "$ART" --iterations 2
python -m strategic_alpha_engine policy --artifacts-dir "$ART"
python -m strategic_alpha_engine status --artifacts-dir "$ART"
```

확인 항목:

- [ ] `research-loop` 가 2회 이상 정상 실행된다.
- [ ] `agenda_queue.total_entries > 0`
- [ ] `policy` 가 family recommendation을 반환한다.
- [ ] `status.loop_status.current_state` 가 기대한 값이다.

## 13. 현재 구현의 한계

아래는 실패가 아니라 현재 설계상 전제다.

- [ ] 기본 smoke test는 여전히 fake Brain adapter 기준이라는 점을 이해하고 있다.
- [ ] `autopilot` 은 LLM endpoint 의 응답 시간과 schema 준수에 의존한다는 점을 이해하고 있다.
- [ ] 실제 외부 API 연동은 `simulate --brain-provider worldquant` 또는 `autopilot --brain-provider worldquant` 로 별도 검증해야 한다는 점을 이해하고 있다.
- [ ] packet에는 lineage와 rationale이 들어가므로 외부 공유 전에 민감 정보 검토가 필요하다.
- [ ] 실제 외부 제출 자동화는 아직 구현되지 않았다는 점을 이해하고 있다.

## 14. Go / No-Go 기준

배포 전 또는 다음 구현 단계로 넘어가기 전 아래를 만족하면 `Go`다.

- [ ] `pytest -q` 전체 통과
- [ ] end-to-end smoke test 전체 성공
- [ ] autopilot smoke test 성공
- [ ] status 요약 간 수치 충돌 없음
- [ ] artifact와 state 파일 생성 확인
- [ ] packet lineage 검토 완료
- [ ] autopilot manifest와 packet index 검토 완료
- [ ] 예외 시나리오 최소 2개 이상 확인

아래 중 하나라도 해당하면 `No-Go`다.

- [ ] 같은 candidate의 lineage가 artifact마다 다르다.
- [ ] stage count와 inventory summary가 서로 맞지 않는다.
- [ ] review approve 이후 packet 생성이 되지 않는다.
- [ ] packet이 self-contained하지 않다.
- [ ] `latest_submission_manifest.json` 이 생성되었는데 `submission_packets.jsonl` 과 내용이 맞지 않는다.
- [ ] 테스트는 통과하지만 CLI smoke에서 실제 파일이 생성되지 않는다.

## 15. 권장 기록

점검 후 아래만 간단히 남겨두면 된다.

- 점검 일시:
- 점검 브랜치:
- `pytest -q` 결과:
- smoke test artifact root:
- autopilot smoke artifact root:
- hold/reject 추가 점검 여부:
- 최종 판단: `Go` / `No-Go`
