# Strategic Alpha Research Engine Phase 5 구현 범위

## 1. 문서 목적

이 문서는 Phase 4 다음 단계로 구현할 `submission prep layer` 범위를 고정하기 위한 문서다.

이번 단계의 핵심 목표는 다음이다.

- robust candidate를 사람이 검토하고 제출 준비 상태로 승격하는 흐름을 만들기
- `promote -> human review -> submission packet generation`
  경로를 코드상에서 명시적으로 남기기
- 제출 직전 후보의 lineage, validation 근거, review 결정이
  하나의 패킷으로 재구성 가능하게 만들기

## 2. 이번 단계의 목표

이번 단계는 아래를 달성해야 한다.

1. submission-ready 상태 기록 구조 추가
2. human review queue와 review decision 기록 추가
3. submission packet artifact 생성 기능 추가
4. `promote` 실행 모드의 최종 버전 구현
5. submission 후보의 lineage / validation summary / review summary를 하나로 묶기
6. pytest 기준 단위 테스트와 packet smoke test 추가

## 3. 이번 단계 in-scope

### 3.1 Submission-ready ledger

포함:
- `robust_candidate -> submission_ready` 전이 기록
- submission-ready candidate inventory
- final stage counts 및 최근 승격 기록

### 3.2 Human review queue

포함:
- review queue entry
- review status
- approve / reject / hold decision 기록
- review notes와 rationale 보존

### 3.3 Submission packet generation

포함:
- hypothesis / blueprint / candidate lineage
- critique / simulation / validation 요약
- promotion decision 요약
- human review 결과
- 최종 제출용 JSON packet 또는 동등한 artifact

### 3.4 Promote / report workflow

포함:
- `promote` CLI의 submission-ready 업데이트
- review queue를 반영한 최종 상태 갱신
- status에서 submission-ready pool 확인

### 3.5 운영 문서 / runbook

포함:
- review 절차 문서
- packet 생성 및 검토 순서
- artifact 민감도와 보존 정책

### 3.6 Test

포함:
- review queue 상태 전이 테스트
- submission-ready 승격 테스트
- packet generation schema 테스트
- promote / packet smoke test

## 4. 이번 단계 out-of-scope

아래는 이번 단계에서 제외한다.

1. 외부 플랫폼으로의 자동 제출
2. 웹 기반 review UI
3. 멀티 유저 승인 시스템
4. 권한/감사 로그의 enterprise 확장 버전

## 5. 세부 브랜치 단위

이번 단계는 로드맵 기준으로 아래 브랜치에 대응한다.

1. `phase5/5-1-submission-ready-ledger`
2. `phase5/5-2-human-review-queue`
3. `phase5/5-3-submission-packet-generation`

## 5.1 현재 구현 진척

- `5-1 submission-ready ledger`: 완료
- `5-2 human review queue`: 완료
- 현재까지 구현된 내용:
  - `robust_candidate -> submission_ready` 승격 workflow
  - `promote` CLI
  - `submission_ready.jsonl` artifact와 `submission_ready_candidates.jsonl` state ledger
  - `status`의 `submission_ready_inventory` 요약
  - promote 시점의 pending `human_review_queue`
  - `review` CLI와 `human_review_decisions.jsonl`
  - `status`의 `human_review_queue`, `human_review_summary` 요약
- 다음 작업:
  - `5-3 submission packet generation`
  - review 결과를 포함한 self-contained packet 구성
  - packet CLI와 runbook 정리

## 6. 구현 원칙

### 6.1 최종 승격은 불투명하면 안 됨

submission-ready 상태는 반드시 validation과 review 근거를 따라가며 설명 가능해야 한다.

### 6.2 Packet은 self-contained여야 함

외부에 전달하지 않더라도 packet만 보면 후보의 lineage와 핵심 근거를 이해할 수 있어야 한다.

### 6.3 Human review는 optional이 아니라 명시적 단계

rule-based promotion만으로 최종 제출 상태를 만들지 않는다.

### 6.4 Review와 artifact는 분리하되 연결 가능해야 함

queue entry, review decision, submission packet이 서로 링크되지만
각각 별도 레코드로 추적 가능해야 한다.

## 7. 완료 산출물

이번 단계 완료 시점에 있어야 하는 것:

1. submission-ready ledger
2. human review queue / decision 구조
3. submission packet generator
4. `promote` CLI의 최종 버전
5. review / packet runbook
6. pytest 통과

## 8. 성공 기준

이번 단계는 아래를 만족하면 성공이다.

1. robust candidate를 submission-ready로 명시적으로 승격할 수 있다.
2. human review 결과가 최종 상태에 반영된다.
3. submission packet 하나로 lineage와 검증 요약을 재구성할 수 있다.
4. status에서 submission-ready pool과 review queue를 확인할 수 있다.
5. 이후 실제 제출 자동화가 붙더라도 현재 packet/ledger 구조를 재사용할 수 있다.

## 9. 한 줄 요약

이번 단계는 "검증 통과 후보를 사람이 검토하고 제출 가능한 형태로 포장하는 마지막 운영 레이어를 만드는 단계"다.
