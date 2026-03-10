# Strategic Alpha Research Engine Phase 3 구현 범위

현재 이 문서는 Phase 3 구현 이력을 설명하는 기록 문서다.
현재 운영 경로는 `autopilot` 하나이며,
아래 내용은 이후 `autopilot` agenda generation과 family weighting으로 흡수된 단계적 구현 범위를 정리한다.

## 1. 문서 목적

이 문서는 Phase 2 다음 단계로 구현할 `learning loop` 범위를 고정하기 위한 문서다.

이번 단계의 핵심 목표는 다음이다.

- 단순 run 기록을 넘어서, family 수준에서 무엇이 먹히는지 학습하기
- `family stats -> learner-ready summary -> agenda prioritization`
  흐름을 코드상에서 연결하기
- 이후 robust validation과 submission prep이 붙기 전에
  "어떤 방향을 더 탐색할지"를 시스템이 설명 가능하게 만들기

## 2. 이번 단계의 목표

이번 단계는 아래를 달성해야 한다.

1. family 성과 집계 구조 확장
2. learner 입력용 summary 규격 추가
3. heuristic search policy learner 구현
4. `ResearchAgendaManager` 또는 동등한 agenda prioritization 컴포넌트 추가
5. bounded iterative runner 기초 구현
6. `status`에서 family-level 성과와 queue 상태를 더 잘 보이게 만들기
7. pytest 기준 단위 테스트와 샘플 loop 테스트 추가

## 3. 이번 단계 in-scope

### 3.1 Family stats / analytics summary

포함:
- family별 throughput
- family별 success rate
- family별 median sharpe
- family별 timeout rate
- family별 warning / rejection 경향
- skeleton type / field class combination 단위 요약의 최소 구조

### 3.2 Search policy learner

포함:
- simple heuristic bandit 또는 동등한 규칙 기반 learner
- explore / exploit 점수 계산
- 최근 실패 family에 대한 penalty
- 최근 성공 family에 대한 bonus
- learner output explanation 필드

### 3.3 Agenda prioritization

포함:
- seed agenda 유지
- family stats 기반 agenda 재정렬
- 운영자 수동 directive와 learner 점수의 병합 규칙
- "다음에 무엇을 탐색할지"를 설명 가능한 형태로 반환

### 3.4 bounded iterative runner

포함:
- bounded iteration 형태의 최소 exploratory runner
- `agenda selection -> synthesis -> simulation -> evaluation -> update stats`
  흐름 연결
- loop 1회 또는 N회 실행
- 각 iteration의 run state와 status summary 갱신

### 3.5 Status / report 확장

포함:
- family별 success / timeout / rejection 요약
- agenda queue 상태
- 현재 active loop 상태
- 최근 24시간 candidate 흐름의 family별 분포

### 3.6 Test

포함:
- family aggregation 단위 테스트
- learner scoring 테스트
- agenda prioritization 테스트
- bounded runner smoke test

## 4. 이번 단계 out-of-scope

아래는 이번 단계에서 제외한다.

1. contextual bandit
2. Thompson sampling
3. Bayesian optimization
4. multi-period validation
5. submission-ready promotion
6. human review queue
7. 실제 external scheduler

## 5. 세부 브랜치 단위

이번 단계는 로드맵 기준으로 아래 브랜치에 대응한다.

1. `phase3/3-1-family-stats-ledger`
2. `phase3/3-2-search-policy-learner`
3. `phase3/3-3-agenda-manager-and-research-loop`

현재 진행 상태:

- `3-1 family stats ledger`: 완료
- `3-2 search policy learner`: 완료
- `3-3 agenda manager and research-loop`: 완료
- Phase 3 구현 범위 완료

## 6. 구현 원칙

### 6.1 식 단위보다 family 단위 우선

초기 learner는 식 하나하나를 학습하기보다
family / archetype / skeleton / field-class 조합 수준의 요약을 먼저 본다.

### 6.2 복잡한 ML보다 설명 가능한 heuristic 우선

Phase 3에서는 "왜 이 family를 더 탐색하는지"를 사람이 읽을 수 있어야 한다.

### 6.3 Loop는 재현 가능해야 함

같은 artifact/state 입력이 주어지면 같은 prioritization 결과가 나와야 한다.

### 6.4 Search policy는 실패도 학습해야 함

성공률뿐 아니라 timeout, critic rejection, duplicate 경향도 policy 입력에 포함한다.

## 7. 완료 산출물

이번 단계 완료 시점에 있어야 하는 것:

1. family stats 확장 모델 또는 summary 구조
2. heuristic learner 구현
3. agenda prioritization 컴포넌트
4. bounded iterative runner 또는 동등한 진입점
5. status summary 확장
6. pytest 통과

## 8. 성공 기준

이번 단계는 아래를 만족하면 성공이다.

1. family 성과를 바탕으로 agenda priority를 재조정할 수 있다.
2. learner가 다음 탐색 대상을 설명 가능한 이유와 함께 반환한다.
3. bounded iterative runner를 실행할 수 있다.
4. `status`에서 family별 성과 요약과 loop 상태를 볼 수 있다.
5. 이후 Phase 4 validation 단계가 family-level signal을 그대로 재사용할 수 있다.

## 9. 한 줄 요약

이번 단계는 "무작정 더 생성하는 대신, 무엇을 더 탐색해야 하는지 학습하는 구조를 만드는 단계"다.
