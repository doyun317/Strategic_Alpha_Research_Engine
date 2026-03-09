# Strategic Alpha Research Engine 타겟 아키텍처 Spec

## 문서 메타데이터
- 문서 목적: 기존 `generation_two`를 개선하는 것이 아니라, 레거시 코드 구조를 버리고 완전히 새 프로젝트로 재구축하기 위한 타겟 아키텍처 정의
- 문서 성격: Greenfield target architecture spec
- 작성 기준: 단일 호스트 로컬 운영, 외부 vLLM endpoint 사용, WorldQuant Brain 기반 연구/시뮬레이션/후보 관리
- 비고: 본 문서는 기존 `generation_one`, `generation_two`의 코드 구조를 유지하거나 호환하는 것을 목표로 하지 않는다

## 1. 설계 전제

이 문서는 현재 시스템을 "조금 정리해서 계속 쓰는" 방향이 아니라, 아래 전제를 둔다.

1. 현재 코드 구조는 폐기 대상이다.
2. 기존 코드에서 재사용 가능한 것은 "아이디어"와 "운영에서 얻은 실패 교훈"이지, 모듈 구조가 아니다.
3. 새 시스템은 처음부터 `전략적 연구 엔진`으로 설계한다.
4. 식(expression)을 직접 생성하는 시스템이 아니라, `가설 -> 설계도 -> 후보식 -> 비평 -> 검증 -> 승격` 파이프라인을 가진 시스템으로 설계한다.
5. 모든 생성 결과는 추적 가능해야 하며, "왜 이 알파가 나왔는가"를 역추적할 수 있어야 한다.

## 2. 문제 정의

현재류 시스템의 본질적 문제는 다음과 같다.

- LLM이 거의 직접 식을 만든다.
- 식이 어떤 경제적 가설을 테스트하는지 구조적으로 남지 않는다.
- 데이터 주기와 연산자의 적합성을 체계적으로 검증하지 않는다.
- 탐색 정책이 사실상 랜덤 샘플링에 가깝다.
- 개별 수식 성과만 보고, 어떤 연구 family가 먹히는지 학습하지 않는다.

사람은 보통 알파를 다음 순서로 만든다.

1. 시장 비효율 또는 경제 논리를 정한다.
2. 그 논리가 어떤 시간축에서 작동할지 정한다.
3. 이를 관측할 프록시 데이터를 고른다.
4. raw 값을 변화량, 비율, 스프레드, 정규화된 신호로 바꾼다.
5. outlier, 리스크, 중복 노출을 제어한다.
6. 같은 thesis에서 여러 변형을 만든다.
7. 결과를 보고 "어떤 종류의 가설이 먹히는지"를 학습한다.

새 시스템은 이 사고 과정을 시스템 구조로 강제해야 한다.

## 3. 시스템 목표

새 프로젝트의 목표는 다음과 같다.

1. 전략적으로 알파를 탐색한다.
2. 모든 expression이 명시적 가설과 설계도를 갖도록 한다.
3. 데이터 특성과 시간축이 맞지 않는 저품질 식을 시뮬레이션 전 차단한다.
4. 단일 수식 점수보다 `가설 family 수준의 학습`을 수행한다.
5. 좋은 알파를 찾는 것뿐 아니라, 왜 좋은지와 어디서 왔는지를 남긴다.
6. 제출 후보는 단순 threshold 통과가 아니라 다단계 승격 파이프라인을 통해 선별한다.

## 4. 비목표

명시적으로 목표가 아닌 것:

1. 기존 `generation_two` 모듈 경계 유지
2. 기존 클래스/함수 이름 유지
3. Ollama 호환성 유지
4. GUI 우선 개발
5. Docker 우선 설계
6. "expression 하나 빨리 뽑기" 최적화
7. WorldQuant 자동 제출 자동화

## 5. 핵심 설계 원칙

### 5.1 Expression-First 금지

시스템은 처음부터 expression을 만들면 안 된다.

반드시 다음 순서를 강제한다.

`Research Agenda -> Hypothesis Spec -> Signal Blueprint -> Expression Candidates`

### 5.2 구조화 출력 우선

LLM 출력은 자유 텍스트가 아니라 가능한 한 JSON schema를 강제한다.

예:
- hypothesis JSON
- blueprint JSON
- critique JSON
- promotion decision JSON

### 5.3 모든 결과의 계보 추적

모든 expression은 아래 상위 객체를 참조해야 한다.

- 어떤 agenda에서 나왔는가
- 어떤 hypothesis에서 파생됐는가
- 어떤 blueprint에서 생성됐는가
- 어떤 critic을 통과했는가
- 어떤 validation 결과를 받았는가

### 5.4 사람의 연구 과정과 유사한 단계 분리

시스템은 다음 역할을 명확히 분리해야 한다.

- 연구 주제 선정
- 가설 정식화
- 데이터/연산 설계
- expression 합성
- 전략적 비평
- 시뮬레이션 실행
- family 수준 학습
- 후보 승격

### 5.5 전략적 탐색 정책 내장

탐색은 균등 랜덤이 아니라 학습 기반이어야 한다.

예:
- 잘 먹히는 family를 더 깊게 탐색
- 실패율/timeout/warning이 높은 family는 감점
- 데이터 주기와 horizon이 맞는 family를 우선

### 5.6 Artifact-First 운영

모든 단계는 상태를 메모리에만 두지 않고 artifact로 남긴다.

예:
- hypothesis spec
- blueprint
- expression candidate
- critique report
- simulation result
- validation result
- promotion decision

## 6. 제안하는 새 프로젝트 개념명

프로젝트 레벨에서 `generation_two`와 분리된 새 이름을 쓰는 것이 맞다.

예시:
- `strategic-alpha-engine`
- `brain-research-engine`
- `alpha-research-lab`
- `wq-strategy-miner`

본 문서에서는 가칭으로 `strategic-alpha-engine`을 사용한다.

## 7. 상위 시스템 개념

새 시스템은 다음 역할을 가진다.

1. 연구 아젠다를 생성 또는 선택한다.
2. 아젠다를 구조화된 가설로 만든다.
3. 가설에 맞는 데이터 및 연산 설계도를 만든다.
4. 설계도 기반으로 소수의 expression 후보를 합성한다.
5. 사람이 보듯 전략적 비평을 수행한다.
6. 통과한 후보만 시뮬레이션한다.
7. 결과를 family 수준으로 학습한다.
8. 다단계 validation을 거쳐 제출 후보 풀을 만든다.

## 8. 상위 아키텍처

```text
[Research Agenda Manager]
        |
        v
[Hypothesis Planner]
        |
        v
[Signal Blueprint Builder]
        |
        v
[Expression Synthesizer]
        |
        v
[Strategic Critic]
        |
        +--> reject / repair
        |
        v
[Simulation Orchestrator]
        |
        v
[Evaluation & Validation Engine]
        |
        v
[Candidate Promotion Pipeline]
        |
        v
[Research Memory + Search Policy Learner]
        |
        +--> updates next agenda selection
```

## 9. 논리 계층 구조

새 프로젝트는 아래 계층을 갖는다.

### 9.1 Domain Layer

순수 도메인 개념과 규칙만 포함한다.

- hypothesis
- blueprint
- candidate
- critique
- validation
- promotion
- family stats
- search policy state

이 계층은 외부 API, DB, HTTP, LLM client에 의존하지 않는다.

### 9.2 Application Layer

유스케이스와 워크플로우를 담당한다.

- hypothesis planning workflow
- blueprint generation workflow
- expression generation workflow
- critique workflow
- simulation workflow
- validation workflow
- promotion workflow

### 9.3 Infrastructure Layer

외부 시스템과 연결되는 어댑터를 둔다.

- vLLM adapter
- WorldQuant Brain adapter
- metadata repository
- artifact repository
- event/logging/metrics

### 9.4 Interface Layer

운영 진입점이다.

- CLI
- headless service runner
- status/report commands
- 추후 필요 시 minimal API server

## 10. 핵심 도메인 객체

### 10.1 ResearchAgenda

연구할 방향의 상위 묶음.

필드 예시:
- `agenda_id`
- `name`
- `family`
- `priority`
- `status`
- `target_region`
- `target_universe`
- `target_horizons`
- `motivation`

### 10.2 HypothesisSpec

경제적 가설의 구조화 객체.

필드 예시:
- `hypothesis_id`
- `agenda_id`
- `family`
- `economic_rationale`
- `expected_direction`
- `horizon`
- `market_context`
- `field_classes`
- `risk_notes`
- `forbidden_patterns`
- `confidence`

### 10.3 SignalBlueprint

가설을 실제 데이터 및 연산 설계로 내린 객체.

필드 예시:
- `blueprint_id`
- `hypothesis_id`
- `primary_fields`
- `secondary_fields`
- `field_roles`
- `transform_plan`
- `normalization_plan`
- `risk_control_plan`
- `operator_constraints`
- `skeleton_templates`
- `disallowed_patterns`

### 10.4 ExpressionCandidate

실제 FASTEXPR 후보식.

필드 예시:
- `candidate_id`
- `blueprint_id`
- `expression`
- `generation_method`
- `normalized_expression`
- `complexity_score`
- `outer_normalization_present`
- `field_update_alignment_score`
- `duplicate_group_key`

### 10.5 CritiqueReport

전략적 비평 결과.

필드 예시:
- `critique_id`
- `candidate_id`
- `passes`
- `issues`
- `severity`
- `repair_suggestions`
- `structural_quality_score`
- `economic_coherence_score`
- `data_horizon_alignment_score`

### 10.6 SimulationRun

시뮬레이션 요청과 실행 상태.

필드 예시:
- `simulation_run_id`
- `candidate_id`
- `region`
- `universe`
- `delay`
- `neutralization`
- `test_period`
- `status`
- `submitted_at`
- `completed_at`
- `provider_run_id`

### 10.7 ValidationRecord

1차 또는 2차 검증 결과.

필드 예시:
- `validation_id`
- `candidate_id`
- `validation_stage`
- `period`
- `sharpe`
- `fitness`
- `turnover`
- `returns`
- `drawdown`
- `checks`
- `grade`
- `pass_decision`

### 10.8 PromotionDecision

후보 승격 결과.

필드 예시:
- `promotion_id`
- `candidate_id`
- `from_stage`
- `to_stage`
- `decision`
- `reasons`
- `decided_at`

## 11. 기능 컴포넌트 정의

## 11.1 Research Agenda Manager

역할:
- 어떤 family를 다음에 탐색할지 정한다.
- 운영자가 seed agenda를 직접 넣을 수도 있게 한다.
- search policy learner의 결과를 받아 agenda 우선순위를 조정한다.

입력:
- family performance stats
- recent success/failure patterns
- 운영자 수동 directive

출력:
- 다음 hypothesis planning 대상으로 쓸 agenda

## 11.2 Hypothesis Planner

역할:
- agenda를 바탕으로 구체적인 가설을 JSON으로 만든다.
- 사람의 연구 메모처럼 경제 논리를 언어적으로 명시한다.

예시 출력:
```json
{
  "family": "quality_deterioration",
  "economic_rationale": "firms with weakening cash generation relative to leverage tend to underperform",
  "expected_direction": "worse quality -> lower returns",
  "horizon": "medium",
  "field_classes": ["fundamental", "price"],
  "forbidden_patterns": ["short_delay_on_slow_fundamentals", "raw_level_only"]
}
```

## 11.3 Metadata Intelligence Layer

이 계층은 새 프로젝트에서 매우 중요하다.

필수 메타데이터:
- field class
- update cadence
- recommended horizon
- discouraged transforms
- safe lookback range
- normalization recommendation
- outlier risk

예:
- `debt_lt`
  - class: `fundamental`
  - update cadence: `slow`
  - discouraged transforms: `short_delay`, `short_sum`

이 정보가 있어야 `ts_sum(debt_lt, 10)` 같은 pseudo-time-series를 시뮬레이션 전에 잡아낼 수 있다.

## 11.4 Signal Blueprint Builder

역할:
- HypothesisSpec을 실제 데이터/연산 설계로 변환

예시:
- thesis: `quality deterioration`
- fields: `cashflow_op`, `debt_lt`, `equity`
- transforms: `delta_63`, `ratio`, `spread`
- normalization: `outer_rank`
- risk control: `winsor-like normalization or rank`

출력은 자유식이 아니라 blueprint JSON이어야 한다.

## 11.5 Expression Synthesizer

역할:
- blueprint를 FASTEXPR expression 후보로 내린다.

중요 원칙:
- LLM에게 자유 생성시키지 않는다.
- skeleton + slot filling 기반으로 합성한다.
- 한 blueprint에서 1개가 아니라 3~10개 후보를 만들 수 있다.

예시 skeleton:
- `rank(ts_zscore(ts_delta(FIELD_A, D1), D2))`
- `rank(divide(ts_delta(FIELD_A, D1), add(ts_std_dev(FIELD_A, D2), C)))`
- `rank(subtract(ts_rank(FIELD_A, D1), ts_rank(ts_delay(FIELD_B, D2), D1)))`
- `rank(divide(subtract(FIELD_A, FIELD_B), add(abs(FIELD_C), C)))`

## 11.6 Strategic Critic

역할:
- 사람이 연구 노트를 검토하듯 후보식을 비평한다.

검사 예시:
- 느린 fundamental에 5일 delay 사용 여부
- 사실상 상수배에 불과한 sum 사용 여부
- outer `rank()` 또는 동등 정규화의 부재
- raw level이 outlier를 지배할 위험
- thesis와 sign이 일치하는지
- blueprint 의도와 expression이 일치하는지
- 복잡도 과다 여부

이 계층은 rule-based critic + LLM critic의 혼합 구조가 좋다.

### Rule-based critic 예시
- `field.update_cadence == slow` and `operator == ts_delay` and `lookback < 20` -> reject
- `field.update_cadence == slow` and `operator == ts_sum` and `lookback < 63` -> reject
- `outer_rank == false` and `raw_ratio == true` -> penalize

### LLM critic 예시
- 이 수식이 실제로 새 정보를 담는가
- 이 수식은 단순 scaling trick 아닌가
- thesis를 설득력 있게 측정하는가

## 11.7 Static Validator

역할:
- 전략적 critic과 별개로 compiler-safe 검사 수행

검사 항목:
- operator 존재 여부
- arity
- constant arg
- 괄호 균형
- 문자셋
- allowed operator set
- allowed field set

현재 시스템의 precheck에 해당하지만, 새 프로젝트에서는 별도 독립 모듈이어야 한다.

## 11.8 Simulation Orchestrator

역할:
- Brain submission 요청 생성
- 상태 polling
- result fetch
- timeout 및 retry 제어

새 프로젝트 원칙:
- 시뮬레이션 settings는 immutable request object로 취급
- runtime config가 실제 request를 덮어쓰지 않음
- `universe` overwrite 같은 hidden mutation 금지

## 11.9 Evaluation & Validation Engine

역할:
- 1차 탐색 결과와 다중 기간 재검증 결과를 분리 관리

검증 단계 예시:

1. Stage A: fast exploration
   - `P1Y0M0D`
2. Stage B: robustness validation
   - `P3Y0M0D`
   - `P5Y0M0D`
3. Stage C: detailed check validation
   - `checks`
   - `grade`
   - `train/test/is` 또는 대응 구조

## 11.10 Candidate Promotion Pipeline

역할:
- 좋은 수식을 단순히 hopeful에 append하지 않고 단계적으로 승격

추천 단계:
- `draft`
- `critique_passed`
- `sim_passed`
- `robust_candidate`
- `submission_ready`
- `rejected`

승격은 rule-based + optional human review로 처리한다.

## 11.11 Search Policy Learner

역할:
- family 수준에서 무엇을 더 파야 하는지 학습

추적 지표:
- family별 success rate
- family별 median sharpe
- family별 ready-rate
- family별 timeout rate
- family별 warning rate
- field class 조합별 성과
- skeleton별 성과

추천 초기 정책:
- simple heuristic bandit
- 이후 contextual bandit 또는 Bayesian optimizer로 확장 가능

## 12. 데이터 저장소 아키텍처

새 프로젝트는 persistence를 명시적으로 분리해야 한다.

### 12.1 Metadata Store

저장 대상:
- operators
- fields
- field metadata
- transform rules
- hypothesis family catalog

### 12.2 Artifact Store

저장 대상:
- hypothesis specs
- blueprints
- critiques
- raw LLM outputs
- simulation raw responses

권장 방식:
- 파일 기반 artifact store
- JSON 또는 JSONL
- run_id / candidate_id 기반 경로 구조

### 12.3 State Store

저장 대상:
- candidate lifecycle state
- promotion decisions
- family statistics
- run state

권장 초기안:
- SQLite

이유:
- 단일 호스트 운영에 충분
- 개발 속도 빠름
- 운영 난이도 낮음

추후 확장안:
- PostgreSQL

### 12.4 Analytics Store

저장 대상:
- 결과 집계
- family performance
- validation matrix

권장 초기안:
- SQLite + materialized summary table

## 13. 프로젝트 디렉터리 구조 제안

```text
strategic-alpha-engine/
  pyproject.toml
  README.md
  settings/
    default.env
    local.env.example
  docs/
    architecture/
    runbooks/
    prompts/
  src/strategic_alpha_engine/
    domain/
      models/
      rules/
      policies/
    application/
      workflows/
      services/
      use_cases/
    infrastructure/
      llm/
      brain/
      repositories/
      storage/
      telemetry/
    interfaces/
      cli/
      service/
    prompts/
      planner/
      blueprint/
      critic/
    config/
  tests/
    unit/
    integration/
    e2e/
  data/
  artifacts/
  logs/
```

## 14. 실행 모드 정의

새 프로젝트는 최소 아래 실행 모드를 가져야 한다.

### 14.1 `plan`
- agenda 선택
- hypothesis 생성
- blueprint 생성
- 아직 시뮬레이션하지 않음

### 14.2 `synthesize`
- blueprint로부터 expression 후보 생성
- critic까지 수행

### 14.3 `simulate`
- critique 통과 후보만 시뮬레이션

### 14.4 `research-once`
- 한 번의 full pipeline 실행

### 14.5 `research-loop`
- continuous 연구 루프

### 14.6 `validate`
- 상위 후보 다중 기간 재검증

### 14.7 `promote`
- submission-ready candidate pool 업데이트

### 14.8 `status`
- agenda 상태
- family stats
- validation backlog
- candidate stage counts

## 15. LLM 사용 전략

LLM은 "expression 생성기"가 아니라 여러 역할로 분리해 써야 한다.

### 15.1 Planner Role
- hypothesis 생성
- output: JSON only

### 15.2 Blueprint Role
- hypothesis를 데이터/연산 설계로 변환
- output: JSON only

### 15.3 Synthesizer Role
- blueprint를 제한된 grammar에 맞는 expression으로 합성
- output: expression candidates

### 15.4 Critic Role
- 전략적 비평
- output: structured critique JSON

중요:
- 같은 모델을 쓰더라도 role과 prompt는 분리한다.
- temperature도 역할별로 다르게 둔다.
  - planner: 중간
  - blueprint: 낮음~중간
  - synthesizer: 낮음
  - critic: 낮음

## 16. 프롬프트 설계 원칙

### 16.1 자유형 장문 프롬프트 금지

각 단계별 입력과 출력 schema를 작게 유지한다.

### 16.2 최근 성공 패턴은 "복붙"이 아니라 요약 신호로만 제공

예:
- overused operators
- overused head shapes
- underexplored field classes

### 16.3 프롬프트는 역할별로 완전히 분리

planner prompt, blueprint prompt, critic prompt는 파일 단위로 분리 저장한다.

### 16.4 모든 프롬프트는 테스트 가능해야 함

golden sample 기반으로:
- JSON 파싱 성공률
- invalid output 비율
- duplicate 비율
- critic agreement 비율
을 테스트한다.

## 17. 전략적 탐색 정책

새 시스템의 핵심 차별점은 search policy에 있다.

### 17.1 탐색 단위

식 단위가 아니라 아래 단위를 추적한다.

- family
- hypothesis archetype
- blueprint type
- skeleton type
- field-class combination

### 17.2 추천 초기 정책

초기 구현은 아래 heuristic으로 충분하다.

1. 최근 성과가 좋은 family의 sampling weight 증가
2. timeout/warning이 잦은 family의 weight 감소
3. duplicate가 심한 skeleton의 weight 감소
4. 최근 과소탐색된 field class 조합 가중치 증가

### 17.3 확장 정책

장기적으로는 다음으로 확장 가능하다.

- contextual bandit
- Thompson sampling
- Bayesian optimization

## 18. 검증 및 승격 정책

제출 후보는 단순히 한 번 수치가 좋다고 승격하면 안 된다.

### 18.1 Stage A: 탐색 통과

예:
- `Sharpe > 0.7`
- `Fitness > 0.2`
- `Turnover within band`
- critic severe issue 없음

### 18.2 Stage B: 강건성 통과

예:
- `P1Y`, `P3Y`, `P5Y` 중 2개 이상 양호
- warning/check fail 없음
- family 내 과도한 중복 아님

### 18.3 Stage C: 제출 준비

예:
- strict threshold 충족
- checks/grade 양호
- 동일 thesis군 내 diversity 확보
- 수동 review 통과

## 19. 관측성과 운영

새 프로젝트는 시작부터 observability를 설계에 포함해야 한다.

### 19.1 필수 로그 이벤트

- agenda selected
- hypothesis generated
- blueprint generated
- candidate synthesized
- candidate rejected by critic
- candidate submitted
- simulation completed
- validation passed/failed
- promotion decision made

### 19.2 필수 메트릭

- family별 throughput
- family별 success rate
- duplicate rejection rate
- critic rejection rate
- simulation timeout rate
- validation pass rate
- stage별 queue length

### 19.3 상태 리포트

`status` 명령에서 최소 아래를 보여줘야 한다.

- 현재 research loop 상태
- family별 성과 요약
- validation backlog
- promotion stage별 개수
- 최근 24시간 candidate 흐름

## 20. 보안 및 비밀정보 처리

### 20.1 자격증명 저장

- Brain credentials는 env 또는 별도 credential file로 로드
- 저장소에는 절대 평문 커밋 금지

### 20.2 LLM endpoint

- 무인증 내부망 endpoint를 쓰더라도 설정으로 분리
- base URL, timeout, retry, model 모두 config로 관리

### 20.3 Artifact 민감도

raw simulation response와 candidate history는 연구 자산이므로 명시적 보존 정책을 둔다.

## 21. 테스트 전략

### 21.1 Unit Test

대상:
- schema validation
- rule-based critic
- blueprint builder
- duplicate detector
- search policy scoring

### 21.2 Integration Test

대상:
- vLLM structured output parsing
- Brain auth
- simulation submission and polling
- repository persistence

### 21.3 End-to-End Test

대상:
- `research-once`
- `synthesize -> critique -> simulate -> validate`

### 21.4 Regression Test

대상:
- pseudo-time-series on slow fundamentals 차단
- missing outer rank 감점/차단
- duplicate logging semantics
- universe overwrite 금지

## 22. 구현 단계 제안

## Phase 0: Foundation

목표:
- 새 repo 생성
- config / logging / repository 기본 틀
- WorldQuant adapter
- vLLM adapter

산출물:
- CLI skeleton
- persistence skeleton
- operator/field metadata cache

## Phase 1: Strategic Planning MVP

목표:
- hypothesis planner
- blueprint builder
- rule-based critic
- constrained synthesizer

이 단계가 완료되면 기존처럼 거의 랜덤한 식 생성에서 벗어나기 시작한다.

## Phase 2: Simulation Integration

목표:
- immutable simulation request
- simulation orchestrator
- raw response persistence
- Stage A candidate promotion

## Phase 3: Learning Loop

목표:
- family stats
- search policy learner
- agenda prioritization

이 단계부터 "사람처럼 어떤 방향이 먹히는지 학습"하는 구조가 생긴다.

## Phase 4: Robust Validation

목표:
- multi-period validation
- check/grade-aware promotion
- robust candidate pool

## Phase 5: Submission Prep Layer

목표:
- submission-ready stage
- human review queue
- submission packet generation

## 23. 성공 조건

새 프로젝트가 성공적으로 설계되었다고 보기 위한 조건:

1. expression 하나마다 상위 hypothesis와 blueprint를 추적 가능
2. pseudo-time-series 저품질 식이 시뮬레이션 전에 대다수 차단됨
3. 최근 탐색이 family 단위로 편향 조정됨
4. 단순 random formula generation이 아니라 structured generation이 기본 경로가 됨
5. 결과 랭킹뿐 아니라 연구 경로와 실패 원인까지 설명 가능
6. 제출 후보가 다단계 validation을 거쳐 선별됨

## 24. 현재 프로젝트로부터 가져올 것과 버릴 것

### 가져올 것

- 운영 경험에서 얻은 실패 패턴
- vLLM endpoint 사용 경험
- Brain API 인증/시뮬레이션 흐름 이해
- candidate ranking 기준 아이디어
- timeout / rate-limit 대응 경험

### 버릴 것

- 현재 module layout
- 현재 `generation_two` 클래스 경계
- expression-first prompt 구조
- file-scan 기반 후보 집계 기본 구조
- legacy `ollama` 네이밍
- 현재 duplicate / precheck / retry의 뒤섞인 제어 흐름

## 25. 최종 결론

새 프로젝트는 "LLM으로 식을 대충 많이 뽑아보는 시스템"이 아니라, "사람 연구자의 사고 과정을 구조화해 반복 실행하는 시스템"이어야 한다.

핵심 구조는 다음 한 줄로 요약할 수 있다.

`가설을 먼저 만들고, 설계도를 만들고, 그 설계도로부터 후보식을 만들고, 전략적으로 비평한 뒤 검증하고, 그 결과를 다시 다음 연구 계획에 반영하는 시스템`

즉 새 프로젝트의 목표는 expression generator가 아니라 `Strategic Alpha Research Engine`이다.
