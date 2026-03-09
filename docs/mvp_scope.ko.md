# Strategic Alpha Research Engine MVP 범위

## 1. 문서 목적

이 문서는 Greenfield 아키텍처 spec을 실제 구현으로 옮길 때, 첫 번째 MVP에서 어디까지 만들고 어디까지 만들지 않을지를 고정하기 위한 문서다.

MVP의 목표는 "전략적 알파 연구 엔진의 전체 비전"을 한 번에 완성하는 것이 아니라, 다음 사이클을 안정적으로 검증할 수 있는 최소 기반을 만드는 것이다.

`Research Agenda -> Hypothesis Spec -> Signal Blueprint -> Candidate Synthesis Contract`

즉, 현재 MVP는 "전략적 생성 이전의 구조화된 연구 입력 계층"을 만드는 단계다.

## 2. MVP 목표

MVP는 아래 목표를 달성해야 한다.

1. 새 프로젝트를 독립적인 Python repo로 시작할 수 있어야 한다.
2. 핵심 도메인 객체가 명시적 schema로 정의되어야 한다.
3. 자유 텍스트가 아니라 구조화된 JSON payload를 시스템의 기본 입출력 형태로 삼아야 한다.
4. 저품질 설계 일부를 schema validation 수준에서 조기에 차단해야 한다.
5. 이후 planner, critic, synthesizer, simulator를 붙일 수 있는 명확한 코드 경계를 가져야 한다.

## 3. MVP in-scope

### 3.1 Repo foundation

포함:
- `pyproject.toml`
- `src/` 기반 패키지 구조
- `tests/` 구조
- `settings/` 디렉터리
- 기본 `README.md`
- `uv` 기반 설치 가능 구조

### 3.2 Domain schema layer

포함:
- `HypothesisSpec`
- `SignalBlueprint`
- supporting enum / sub-schema
- strict validation rules
- JSON schema export 가능 구조

### 3.3 Basic CLI utilities

포함:
- schema 출력
- example payload 출력

이 단계의 CLI는 운영용 runner가 아니라 개발 보조 도구다.

### 3.4 Test coverage for schema rules

포함:
- 정상 HypothesisSpec 생성 테스트
- 정상 SignalBlueprint 생성 테스트
- 구조적 invalid case 테스트

## 4. MVP out-of-scope

아래는 이번 MVP에서 제외한다.

1. 실제 WorldQuant Brain 인증 및 시뮬레이션 호출
2. 실제 vLLM 호출
3. Research Agenda 자동 선택기
4. Hypothesis planner LLM workflow
5. Blueprint builder LLM workflow
6. Expression synthesizer
7. Strategic critic 엔진
8. Search policy learner
9. Candidate promotion pipeline
10. GUI
11. Docker
12. Submission 자동화

## 5. MVP 완료 산출물

MVP 완료 시점에는 최소 아래 산출물이 있어야 한다.

1. 설치 가능한 새 Python 프로젝트
2. architecture spec 문서
3. MVP scope 문서
4. `HypothesisSpec` 구현
5. `SignalBlueprint` 구현
6. JSON schema export CLI
7. 예시 payload 생성 CLI
8. pytest 기반 기본 테스트

## 6. MVP 성공 기준

아래 조건을 만족하면 MVP는 성공이다.

1. `HypothesisSpec`이 사람의 연구 가설을 구조화해 표현할 수 있다.
2. `SignalBlueprint`가 hypothesis를 실제 필드/변환/정규화 설계로 표현할 수 있다.
3. 잘못된 blueprint가 schema validation에서 조기에 막힌다.
4. 개발자가 CLI로 schema와 example payload를 즉시 확인할 수 있다.
5. 이후 planner/critic/simulator 모듈을 붙여도 스키마를 다시 뒤엎지 않아도 된다.

## 7. 이번 MVP에서 꼭 들어가야 하는 검증 규칙

### 7.1 HypothesisSpec

- 필수 field class가 비어 있으면 안 된다.
- 중복 field class는 허용하지 않는다.
- short horizon인데 느린 데이터만 쓰는 경우는 차단하거나 최소한 명시적으로 표현하게 해야 한다.

### 7.2 SignalBlueprint

- primary field는 실제 선택된 field 안에 있어야 한다.
- secondary field도 실제 선택된 field 안에 있어야 한다.
- 동일 field를 primary와 secondary에 동시에 둘 수 없다.
- transform이 참조하는 field는 blueprint의 field selection 안에 있어야 한다.
- outer normalization이 필수인데 final normalization이 없으면 차단한다.
- 느린 field에 짧은 temporal lookback을 쓰는 경우 차단한다.

## 8. MVP 이후 바로 이어질 Phase 1

MVP 다음 단계는 다음이다.

1. `ResearchAgenda`
2. planner prompt contract
3. blueprint builder contract
4. rule-based critic MVP
5. candidate synthesis skeleton library

즉 이번 MVP는 전체 시스템의 시작점이지만, 실제 연구 루프는 다음 단계부터 붙는다.

## 9. 구현 우선순위

실행 순서는 아래가 맞다.

1. repo scaffold
2. domain enums / base models
3. `HypothesisSpec`
4. `SignalBlueprint`
5. tests
6. CLI schema/example export
7. docs polish

## 10. 한 줄 요약

이번 MVP는 "알파를 생성하는 시스템"을 만드는 단계가 아니라, "알파를 전략적으로 생성하기 위한 구조화된 연구 입력 계층"을 만드는 단계다.

