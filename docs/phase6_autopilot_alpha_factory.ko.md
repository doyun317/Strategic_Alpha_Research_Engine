# Strategic Alpha Research Engine Phase 6 구현 범위

## 1. 문서 목적

이 문서는 Phase 5 다음 단계로 구현한 `autopilot alpha factory` 범위를 고정하기 위한 문서다.

이번 단계의 핵심 목표는 다음이다.

- agenda 생성부터 packet 저장까지를 하나의 실행 모드로 묶기
- `LLM plan/synthesize/critic -> WorldQuant simulate -> validate -> robust 선별 -> auto review -> packet + manifest`
  경로를 코드상에서 명시적으로 연결하기
- 운영자가 실행 후 `latest_submission_manifest.json`과 packet만 보고 제출 후보를 검토할 수 있게 만들기

## 2. 이번 단계의 목표

이번 단계는 아래를 달성해야 한다.

1. `AutopilotSettings`와 관련 runtime env 키 추가
2. `StructuredLLMClient`와 LLM-backed planner / blueprint / critic 구현
3. hybrid agenda generator 추가
4. `autopilot` 실행 모드 추가
5. synthetic auto-review와 packet selection 규칙 추가
6. submission manifest / cumulative packet index 저장 구조 추가
7. pytest 기준 단위 테스트와 fake provider smoke test 추가

## 3. 이번 단계 in-scope

### 3.1 Runtime / settings

포함:
- `SAE_AUTOPILOT_*` env 키
- `RunKind.AUTOPILOT`
- `RunStateRecord.parent_run_id`
- autopilot stop reason enum

### 3.2 Structured LLM adapters

포함:
- OpenAI-compatible structured JSON client
- schema validation retry
- planner / blueprint / critic LLM-backed service
- `agenda_generator` prompt asset과 golden sample

### 3.3 Hybrid agenda generation

포함:
- deterministic template agenda generation
- family stats 기반 LLM agenda augmentation
- queue depth 기반 augment trigger
- agenda dedupe key 고정

### 3.4 Autopilot workflow

포함:
- umbrella autopilot run과 subrun lineage
- iteration별 `plan -> synthesize -> simulate -> validate -> robust promotion`
- stop 조건:
  - `target_packet_count_reached`
  - `idle_round_limit_reached`
  - `max_agendas_reached`
  - `max_simulations_reached`
  - `agenda_generation_exhausted`

### 3.5 Auto review / packet selection

포함:
- `robust_candidate` 이상 후보만 packet 대상으로 선택
- synthetic `submission_ready` 승격
- synthetic approve review
- run별 top-K packet 선택
- cumulative signature dedupe

### 3.6 Manifest / status

포함:
- `autopilot_iterations.jsonl`
- `autopilot_manifest.json`
- `auto_review.jsonl`
- `submission_packet_index.jsonl`
- `latest_submission_manifest.json`
- `status`의 `autopilot_status`, `submission_packet_index`, `latest_submission_manifest`

### 3.7 Runbook / smoke

포함:
- fake provider 전체 smoke 절차
- worldquant 제한 smoke 절차
- 운영 체크리스트 확장

## 4. 이번 단계 out-of-scope

아래는 이번 단계에서 제외한다.

1. 실제 외부 제출 호출 자동화
2. human review UI
3. multi-user approval workflow
4. portfolio construction / execution integration

## 5. 세부 작업 스트림

이번 단계는 계획상 아래 workstream을 포함한다.

1. `6-1 autopilot doc and settings`
2. `6-2 structured LLM adapters`
3. `6-3 hybrid agenda generator`
4. `6-4 autopilot workflow core`
5. `6-5 auto review and packet selection`
6. `6-6 manifest index and status`
7. `6-7 runbook and live smoke`

현재 구현 상태:

- `6-1`: 완료
- `6-2`: 완료
- `6-3`: 완료
- `6-4`: 완료
- `6-5`: 완료
- `6-6`: 완료
- `6-7`: 문서와 fake-provider smoke 범위 완료

## 6. 구현 원칙

### 6.1 기존 수동 CLI는 유지

`simulate`, `validate`, `promote`, `review`, `packet`, `research-loop`를 없애지 않고,
운영용 자동화는 `autopilot`으로 분리한다.

### 6.2 Auto review도 lineage를 남김

자동 승인이라도 기존 review artifact를 우회하지 않고
synthetic review decision으로 남긴다.

### 6.3 Packet은 누적 index와 run별 저장을 같이 유지

이번 run의 결과만 보는 용도와
장기간 누적된 최고 후보만 추리는 용도를 분리한다.

### 6.4 Stop 조건은 설명 가능해야 함

autopilot 종료는 항상 명시적 `stopped_reason`으로 남겨야 한다.

## 7. 완료 산출물

이번 단계 완료 시점에 있어야 하는 것:

1. `autopilot` CLI
2. LLM-backed structured generation adapter
3. hybrid agenda generator
4. autopilot iteration / manifest artifact
5. cumulative packet index와 latest submission manifest
6. Phase 6 문서와 runbook
7. pytest 통과

## 8. 성공 기준

이번 단계는 아래를 만족하면 성공이다.

1. 운영자는 `python -m strategic_alpha_engine autopilot` 한 번으로 packet과 manifest를 생성할 수 있다.
2. `status`에서 latest autopilot 상태와 latest submission manifest 경로를 확인할 수 있다.
3. 동일 signature 후보가 여러 번 나와도 cumulative packet index는 최고 rank만 유지한다.
4. fake provider 기준 autopilot end-to-end 테스트가 통과한다.
5. 실제 외부 제출 자동화가 없어도 packet만으로 제출 후보 검토가 가능하다.

## 9. 한 줄 요약

이번 단계는 "알파 연구 파이프라인을 대량 자동 생성기 형태로 묶고, 제출 후보 packet과 manifest를 자동 저장하는 운영 레이어를 추가하는 단계"다.
