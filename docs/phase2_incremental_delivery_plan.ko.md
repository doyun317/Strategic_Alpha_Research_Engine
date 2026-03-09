# Strategic Alpha Research Engine Phase 2 증분 구현 계획

## 1. 문서 목적

이 문서는 `Phase 2`를 한 번에 밀어 넣지 않고, Git 브랜치와 커밋 단위로 잘게 쪼개서 진행하기 위한 실행 계획이다.

목표는 아래 3가지다.

1. 각 단계가 독립적으로 리뷰 가능해야 한다.
2. 각 브랜치가 테스트 가능한 최소 기능 단위를 가져야 한다.
3. 문제가 생기면 어느 단계에서 깨졌는지 즉시 좁힐 수 있어야 한다.

## 2. Git 운영 원칙

- `main`은 항상 실행 가능하고 테스트가 통과하는 상태만 유지한다.
- 기능 개발은 매번 `main`에서 새 브랜치를 따서 시작한다.
- 한 브랜치는 한 책임만 가진다.
- 각 브랜치는 머지 전에 해당 범위 테스트와 CLI smoke test를 통과해야 한다.

권장 흐름:

```bash
git checkout main
git pull origin main
git checkout -b phase2/2-1-config-and-runtime-model
```

## 3. 단계별 브랜치 계획

| 단계 | 브랜치명 | 목표 | 완료 기준 | 상태 |
| --- | --- | --- | --- | --- |
| 2-1 | `phase2/2-1-config-and-runtime-model` | runtime settings 모델과 env 로딩 구조 확정 | 설정 로딩, validation, CLI 확인, 테스트 통과 | `completed` |
| 2-2 | `phase2/2-2-metadata-catalog` | field/operator metadata catalog 추가 | catalog load 가능, 조회 테스트 통과 | `in_progress` |
| 2-3 | `phase2/2-3-static-validator` | critic 이전 정적 validator 추가 | invalid expression 차단 테스트 통과 | `planned` |
| 2-4 | `phase2/2-4-simulation-domain` | `SimulationRequest`, `SimulationRun` 도메인 추가 | immutable request/domain 테스트 통과 | `planned` |
| 2-5 | `phase2/2-5-brain-client-contract` | Brain adapter 인터페이스와 fake client 확정 | fake client 기반 테스트 가능 | `planned` |
| 2-6 | `phase2/2-6-simulation-orchestrator` | accepted candidate 시뮬레이션 orchestration 구현 | submit/poll/result 흐름 테스트 통과 | `planned` |
| 2-7 | `phase2/2-7-artifact-store` | 파일 기반 artifact store 추가 | workflow artifact 저장 확인 | `planned` |
| 2-8 | `phase2/2-8-state-store` | SQLite state store 추가 | candidate/simulation 상태 저장 확인 | `planned` |
| 2-9 | `phase2/2-9-simulate-cli` | `simulate` CLI 추가 | CLI로 시뮬레이션 실행 가능 | `planned` |
| 2-10 | `phase2/2-10-stage-a-promotion` | Stage A 승격 로직 추가 | `draft -> critique_passed -> sim_passed` 전이 확인 | `planned` |
| 2-11 | `phase2/2-11-integration-tests-and-runbook` | 통합 테스트와 운영 문서 정리 | fake e2e 테스트와 runbook 추가 | `planned` |

## 4. 브랜치별 공통 체크리스트

- 관련 단위 테스트가 추가되었는가
- 기존 테스트가 모두 통과하는가
- CLI 또는 진입점에서 직접 확인 가능한가
- 문서 또는 예제 env가 필요한 변경이면 같이 반영했는가
- 다음 브랜치가 이 브랜치의 결과물을 안정적으로 재사용할 수 있는가

## 5. 현재 작업 범위: 2-2

이번 브랜치에서 처리할 내용:

- field metadata 모델 추가
- operator metadata 모델 추가
- seed catalog loader 추가
- catalog filtering/query API 추가
- CLI에서 metadata summary / field excerpt / operator list 확인 가능하게 만들기
- 관련 테스트 추가

이번 브랜치에서 일부러 하지 않는 내용:

- static validator 규칙 집행
- simulation domain
- Brain HTTP 연동
- persistence
- promotion pipeline

## 6. 권장 커밋 단위

`2-2`에서는 아래 정도로 나누는 것이 적절하다.

1. metadata domain 모델 추가
2. seed catalog loader 추가
3. CLI `catalog` 명령 연결
4. README / 계획 문서 상태 업데이트
5. 테스트 추가 및 정리

## 7. 다음 단계 진입 조건

`2-3 static validator`로 넘어가기 전에 아래를 만족해야 한다.

- `pytest` 통과
- `python -m strategic_alpha_engine catalog --view summary` 정상 동작
- field class / horizon 기준 excerpt filtering 가능
- field/operator lookup이 seed catalog 기준으로 안정적으로 동작한다
