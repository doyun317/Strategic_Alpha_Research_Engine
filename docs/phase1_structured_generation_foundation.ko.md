# Strategic Alpha Research Engine Phase 1 구현 범위

## 1. 문서 목적

이 문서는 MVP 다음 단계로 구현할 `structured generation foundation` 범위를 고정하기 위한 문서다.

이번 단계의 핵심 목표는 다음이다.

- 단순 schema 저장소를 넘어서, 실제 연구 흐름의 최소 뼈대를 만들기
- `ResearchAgenda -> HypothesisSpec -> SignalBlueprint -> ExpressionCandidate -> CritiqueReport`
  흐름을 코드상에서 연결하기
- 아직 Brain/vLLM 실제 연동 없이도 "전략적 생성 파이프라인"의 형태를 검증하기

## 2. 이번 단계의 목표

이번 단계는 아래를 달성해야 한다.

1. `ResearchAgenda` 도메인 모델 추가
2. `ExpressionCandidate` 도메인 모델 추가
3. `CritiqueReport` 도메인 모델 추가
4. planner / blueprint builder / synthesizer / critic contract 정의
5. skeleton 기반 candidate synthesizer 구현
6. rule-based strategic critic 구현
7. `research-once` workflow skeleton 구현
8. CLI로 sample `research-once` 실행 가능하게 만들기

## 3. 이번 단계 in-scope

### 3.1 Domain model 확장

포함:
- `ResearchAgenda`
- `ExpressionCandidate`
- `CritiqueIssue`
- `CritiqueReport`

### 3.2 Service contract 정의

포함:
- `HypothesisPlanner`
- `BlueprintBuilder`
- `CandidateSynthesizer`
- `StrategicCritic`

### 3.3 Prompt contract 정의

포함:
- planner prompt input/output schema
- blueprint builder prompt input/output schema
- critic prompt input/output schema

### 3.4 Dev implementation

포함:
- 정적 hypothesis planner
- 정적 blueprint builder
- skeleton-based candidate synthesizer
- rule-based critic

### 3.5 Workflow

포함:
- `ResearchOnceWorkflow`
- sample agenda 기반 실행
- accepted / rejected candidate 분리

### 3.6 Test

포함:
- agenda validation
- synthesizer output
- critic rejection rule
- workflow end-to-end sample

## 4. 이번 단계 out-of-scope

아래는 이번 단계에서 제외한다.

1. 실제 vLLM planner 호출
2. 실제 blueprint builder LLM 호출
3. 실제 Brain simulation
4. promotion pipeline
5. search policy learner
6. multi-period validation
7. artifact repository
8. persistence layer

## 5. 구현 원칙

### 5.1 Contract 먼저

실제 구현보다 contract를 먼저 둔다.

즉 나중에 LLM 기반 planner나 Brain 기반 simulation을 붙여도 현재 workflow orchestration을 바꾸지 않게 해야 한다.

### 5.2 Stub이 아니라 구조적 Stub

정적 planner와 정적 blueprint builder는 임시 구현이지만,
- 입력 타입이 명확하고
- 출력 타입이 strict하고
- 실제 서비스 인터페이스를 흉내내야 한다.

### 5.3 Expression 생성도 자유형 금지

이번 단계의 synthesizer는 skeleton fill 기반으로만 만든다.

### 5.4 Critic은 무조건 동작해야 함

candidate를 만들었으면 critic을 반드시 거쳐야 한다.

## 6. 완료 산출물

이번 단계 완료 시점에 있어야 하는 것:

1. 새로운 도메인 모델 3종
2. service interface 정의
3. prompt contract 정의
4. sample research-once workflow
5. CLI 실행 진입점
6. pytest 통과

## 7. 성공 기준

이번 단계는 아래를 만족하면 성공이다.

1. sample agenda로 research-once를 실행할 수 있다.
2. workflow가 hypothesis, blueprint, candidate, critique를 모두 생성한다.
3. critic이 구조적으로 잘못된 candidate를 reject할 수 있다.
4. synthesizer가 skeleton과 blueprint를 바탕으로 deterministic하게 candidate를 만들 수 있다.
5. 이후 LLM/Brain adapter를 붙여도 contract를 유지할 수 있다.

## 8. 한 줄 요약

이번 단계는 "전략적으로 생성하기 위한 구조를 실제 코드의 workflow로 연결하는 첫 단계"다.

