# Strategic Alpha Research Engine Phase 4 구현 범위

## 1. 문서 목적

이 문서는 Phase 3 다음 단계로 구현할 `robust validation` 범위를 고정하기 위한 문서다.

이번 단계의 핵심 목표는 다음이다.

- Stage A 탐색 통과 후보를 별도의 validation 흐름으로 관리하기
- `validate -> validation record -> robust candidate promotion`
  흐름을 코드상에서 연결하기
- 단일 기간 성과가 아니라 다중 기간과 checks/grade를 포함한
  강건성 평가를 기본 경로로 만들기

## 2. 이번 단계의 목표

이번 단계는 아래를 달성해야 한다.

1. `ValidationRecord` 도메인 모델 추가
2. `validate` 실행 모드 추가
3. Stage B 다중 기간 validation runner 구현
4. Stage C checks / grade 기반 상세 판정 연결
5. `sim_passed -> robust_candidate` 승격 규칙 구현
6. validation backlog와 결과 matrix를 status에서 확인 가능하게 만들기
7. pytest 기준 단위 테스트와 integration smoke test 추가

## 3. 이번 단계 in-scope

### 3.1 Validation domain / contract

포함:
- `ValidationRecord`
- validation stage 구분
- period별 metrics
- checks / grade / pass_decision
- validation artifact persistence

### 3.2 Stage B multi-period validation

포함:
- `P1Y0M0D`, `P3Y0M0D`, `P5Y0M0D` 같은 기간 다중 실행
- 기간별 결과 집계
- 2개 이상 양호 같은 rule-based 합격 규칙의 최소 버전
- validation backlog 소비

### 3.3 Stage C detailed checks

포함:
- checks 기반 fail 판정
- grade 기반 판정
- warning / fail / manual attention 구분의 최소 구조

### 3.4 Robust candidate promotion

포함:
- `sim_passed -> robust_candidate` 전이
- family 내 과도한 중복 차단의 최소 규칙
- validation 결과와 promotion decision의 명시적 연결

### 3.5 CLI / status

포함:
- `validate` CLI
- validation 결과 요약
- backlog 상태 표시
- robust candidate count 표시

### 3.6 Test

포함:
- validation record schema 테스트
- multi-period aggregation 테스트
- checks / grade-aware promotion 테스트
- validate CLI smoke test

## 4. 이번 단계 out-of-scope

아래는 이번 단계에서 제외한다.

1. submission-ready stage
2. human review queue
3. submission packet generation
4. actual external submission
5. UI 기반 review workflow

## 5. 세부 브랜치 단위

이번 단계는 로드맵 기준으로 아래 브랜치에 대응한다.

1. `phase4/4-1-validation-domain-and-cli`
2. `phase4/4-2-multi-period-validation-runner`
3. `phase4/4-3-robust-candidate-promotion`

현재 진행 상태:

- `4-1 validation domain and CLI`: 완료
- `4-2 multi-period validation runner`: 완료
- `4-3 robust candidate promotion`: 완료
- 다음 작업: `5-1 submission-ready ledger`

## 6. 구현 원칙

### 6.1 Stage A와 validation을 분리

simulation exploration 결과와 robust validation 결과를 같은 레코드에 섞지 않는다.

### 6.2 Validation은 append-only로 기록

기간별 validation 결과와 최종 pass/fail은 나중에 다시 계산할 수 있어야 한다.

### 6.3 Pass decision은 metric + check 기반

Sharpe 같은 숫자뿐 아니라 checks/grade도 승격 판단에 포함해야 한다.

### 6.4 Family diversity를 보존

성능이 좋더라도 동일 thesis군 또는 동일 skeleton이 과도하게 몰리면 제한한다.

## 7. 완료 산출물

이번 단계 완료 시점에 있어야 하는 것:

1. `ValidationRecord` 모델과 artifact 저장 구조
2. `validate` workflow / CLI
3. multi-period validation runner
4. robust candidate promotion 규칙
5. validation backlog / matrix status summary
6. pytest 통과

## 8. 성공 기준

이번 단계는 아래를 만족하면 성공이다.

1. `sim_passed` 후보를 다중 기간으로 재검증할 수 있다.
2. validation 결과가 period별로 추적 가능하다.
3. checks / grade가 promotion decision에 반영된다.
4. robust candidate pool이 명시적으로 관리된다.
5. 이후 Phase 5에서 review/submission packet을 만들 수 있을 만큼 lineage가 유지된다.

## 9. 한 줄 요약

이번 단계는 "탐색 통과 후보를 진짜 강건한 후보로 걸러내는 검증 레이어를 만드는 단계"다.
