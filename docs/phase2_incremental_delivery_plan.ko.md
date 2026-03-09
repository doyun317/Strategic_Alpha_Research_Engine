# Strategic Alpha Research Engine 증분 구현 계획

## 1. 문서 목적

이 문서는 `2-2 metadata catalog` 이후 구현 순서를
[target_greenfield_alpha_research_architecture.ko.md](./target_greenfield_alpha_research_architecture.ko.md)
spec에 맞게 다시 정렬한 실행 계획이다.

핵심 원칙은 아래와 같다.

1. 각 브랜치는 한 책임만 가진다.
2. 각 브랜치는 독립적으로 테스트 가능해야 한다.
3. 아키텍처 spec의 컴포넌트 순서를 최대한 보존한다.
4. 저장은 SQLite가 아니라 로컬 파일 기반으로 통일한다.

## 2. 현재 완료 범위

- `2-1` runtime settings / env loading: 완료
- `2-2` metadata catalog: 완료

즉 현재까지는 spec 기준으로 아래까지 왔다.

- Metadata Intelligence Layer 기초
- planner / blueprint / critic contract의 metadata 입력 기반
- 설정 로더와 catalog 조회 CLI

## 3. 저장 전략 재조정

architecture spec에는 `State Store`와 `Analytics Store`의 초기안으로 SQLite가 적혀 있지만,
현재 프로젝트 운영 전제에서는 그것이 필수는 아니다.

이번 프로젝트에서는 아래 원칙으로 간다.

- 메타데이터 저장: repo 내부 seed data + 로컬 파일
- artifact 저장: JSON / JSONL 파일
- state 저장: JSON / JSONL manifest 파일
- analytics 저장: family별 summary JSON 파일

즉 persistence는 모두 단일 호스트 로컬 파일 기반으로 유지한다.

이 선택의 이유:

- 단일 호스트 운영에는 충분하다.
- 사람이 파일을 직접 열어 검토하기 쉽다.
- migration, schema drift, sqlite locking 같은 초기 비용이 없다.
- 브랜치 단위 실험과 rollback이 단순해진다.

초기 권장 디렉터리 구조:

```text
artifacts/
  runs/
    <run_id>/
      agenda.json
      hypothesis.json
      blueprint.json
      candidates.jsonl
      critiques.jsonl
      evaluations.jsonl
      simulations.jsonl
      validations.jsonl
      promotion.jsonl
  state/
    candidate_stages.jsonl
    run_states.jsonl
    family_stats.json
    family_learner_summaries.json
    validation_backlog.jsonl
  reports/
    latest_status.json
```

## 4. Git 운영 원칙

- `main`은 항상 실행 가능하고 테스트가 통과하는 상태만 유지한다.
- 새 기능은 항상 최신 `main`에서 새 브랜치를 따서 시작한다.
- 한 브랜치는 한 책임만 가진다.
- PR 머지 전에는 관련 테스트와 CLI smoke test를 통과해야 한다.

권장 흐름:

```bash
git checkout main
git pull origin main
git checkout -b phase2/2-3-static-validator
```

## 5. Spec 기준 재정렬 원칙

`2-2` 이후는 아래 spec 순서에 맞춰 진행한다.

1. `11.7 Static Validator`
2. `11.8 Simulation Orchestrator`
3. `11.9 Evaluation & Validation Engine`
4. `11.10 Candidate Promotion Pipeline`
5. `11.11 Search Policy Learner`
6. `14 실행 모드`
7. `16 프롬프트 파일 분리와 테스트 가능성`

즉 다음 순서는
`validator -> simulation -> local persistence -> validation -> promotion -> learner -> loop/status`
가 기본 축이다.

## 6. 단계별 브랜치 계획

| 단계 | 브랜치명 | spec 기준 | 목표 | 완료 기준 | 상태 |
| --- | --- | --- | --- | --- | --- |
| 2-1 | `phase2/2-1-config-and-runtime-model` | Phase 0 foundation | runtime settings 모델과 env 로딩 구조 확정 | 설정 로딩, validation, CLI 확인 | `completed` |
| 2-2 | `phase2/2-2-metadata-catalog` | 11.3 Metadata Intelligence Layer | field/operator metadata catalog 추가 | catalog load, filtering, lookup 테스트 통과 | `completed` |
| 2-3 | `phase2/2-3-static-validator` | 11.7 Static Validator | compiler-safe validator 추가 | invalid expression 차단 테스트 통과 | `completed` |
| 2-4 | `phase2/2-4-prompt-assets-and-golden-samples` | 15, 16 Prompt Strategy | planner/blueprint/critic prompt 파일 분리와 golden sample 테스트 기초 추가 | prompt asset 로딩 및 golden sample 테스트 통과 | `completed` |
| 2-5 | `phase2/2-5-plan-and-synthesize-cli` | 14.1, 14.2 실행 모드 | `plan`, `synthesize` CLI 추가 | agenda -> hypothesis -> blueprint / blueprint -> candidate+critique 분리 실행 가능 | `completed` |
| 2-6 | `phase2/2-6-simulation-domain` | 10.6, 11.8 | immutable `SimulationRequest`, `SimulationRun` 도메인 추가 | request/run validation 테스트 통과 | `completed` |
| 2-7 | `phase2/2-7-brain-client-contract` | 9.3, 11.8 | Brain adapter contract와 fake adapter 추가 | fake submit/poll/fetch 테스트 가능 | `completed` |
| 2-8 | `phase2/2-8-simulation-orchestrator` | 11.8 | critique 통과 후보 simulation orchestration 구현 | submit/poll/result 흐름 테스트 통과 | `completed` |
| 2-9 | `phase2/2-9-local-artifact-ledger` | 12.2 Artifact Store | run artifact를 로컬 JSON/JSONL로 저장 | run_id 기준 artifact 저장 확인 | `completed` |
| 2-10 | `phase2/2-10-local-state-ledger` | 12.3 State Store | candidate stage / run state / family stats를 로컬 manifest로 저장 | 상태 전이 기록과 재로딩 확인 | `completed` |
| 2-11 | `phase2/2-11-simulate-and-status-cli` | 14.3, 14.8 실행 모드 | `simulate`, `status` CLI 추가 | simulate 실행과 status summary 출력 가능 | `completed` |
| 2-12 | `phase2/2-12-evaluation-record-and-stage-a-promotion` | 11.9, 11.10 | `EvaluationRecord`와 Stage A 승격 구현 | `draft -> critique_passed -> sim_passed` 전이 확인 | `completed` |
| 3-1 | `phase3/3-1-family-stats-ledger` | Phase 3, 11.11 | family 성과 집계 구조 추가 | family stats 갱신 테스트 통과 | `completed` |
| 3-2 | `phase3/3-2-search-policy-learner` | 11.11 | heuristic search policy learner 추가 | family weighting / prioritization 테스트 통과 | `completed` |
| 3-3 | `phase3/3-3-agenda-manager-and-research-loop` | 11.1, 14.5 | agenda manager와 `research-loop` 기초 추가 | loop 1회 실행 및 agenda selection 확인 | `completed` |
| 4-1 | `phase4/4-1-validation-domain-and-cli` | 10.7, 14.6 | `ValidationRecord` 도메인과 `validate` CLI 추가 | validation input/output 구조 테스트 통과 | `completed` |
| 4-2 | `phase4/4-2-multi-period-validation-runner` | 11.9, Phase 4 | Stage B/C 다중 기간 검증 runner 추가 | `P1Y0M0D`, `P3Y0M0D`, `P5Y0M0D` validation matrix와 aggregate rule 확인 | `completed` |
| 4-3 | `phase4/4-3-robust-candidate-promotion` | 11.10, Phase 4 | robust candidate 승격 규칙 추가 | `sim_passed -> robust_candidate` 전이 확인 | `planned` |
| 5-1 | `phase5/5-1-submission-ready-ledger` | 10.8, Phase 5 | submission-ready 상태 기록 구조 추가 | submission-ready 후보 ledger 생성 확인 | `planned` |
| 5-2 | `phase5/5-2-human-review-queue` | 11.10, Phase 5 | human review queue와 review decision 기록 추가 | review queue entry 생성/해제 테스트 통과 | `planned` |
| 5-3 | `phase5/5-3-submission-packet-generation` | Phase 5 | 제출용 패킷 생성 | candidate lineage + validation summary packet 생성 가능 | `planned` |

## 7. 각 단계의 역할 경계

### 7.1 `2-3 static validator`

포함:

- operator 존재 여부 검사
- arity 검사
- constant arg 검사
- 괄호 균형 검사
- allowed field / allowed operator 검사

제외:

- economic coherence 판단
- horizon 적합성 판단의 고수준 scoring

### 7.2 `2-4 prompt assets and golden samples`

포함:

- planner prompt 파일
- blueprint prompt 파일
- critic prompt 파일
- prompt별 golden sample JSON

제외:

- 실제 LLM HTTP 호출

### 7.3 `2-8 simulation orchestrator`

포함:

- critique 통과 후보만 simulation 대상으로 선정
- submit / poll / fetch
- timeout / retry 최소 정책

제외:

- multi-period validation
- family-level learning

### 7.4 `2-9, 2-10 local persistence`

포함:

- run artifact 저장
- candidate lifecycle 저장
- status summary 생성

제외:

- DB migration
- SQL layer

## 8. 브랜치별 공통 체크리스트

- 관련 단위 테스트가 추가되었는가
- 기존 테스트가 모두 통과하는가
- CLI 또는 진입점에서 직접 확인 가능한가
- 문서 또는 예제 파일이 필요한 변경이면 같이 반영했는가
- 다음 브랜치가 현재 브랜치 결과물을 안정적으로 재사용할 수 있는가
- 로컬 파일 저장 포맷이 사람이 직접 읽을 수 있는가

## 9. 현재 작업 범위: 4-3

다음 브랜치에서 처리할 내용:

- robust candidate promotion 규칙 추가
- validation matrix를 promotion decision과 명시적으로 연결
- family diversity / duplicate thesis 제한의 최소 규칙 추가
- `sim_passed -> robust_candidate` 상태 전이와 artifact 기록 추가
- 관련 단위 테스트와 CLI smoke test 추가

이번 브랜치에서 일부러 하지 않는 내용:

- submission-ready 판단
- human review queue
- actual submission packet generation
- UI review workflow

## 10. `4-3` 권장 커밋 단위

1. robust candidate promotion workflow 추가
2. family diversity / duplicate guard 추가
3. promotion artifact와 status summary 확장
4. 문서 상태 업데이트

## 11. `4-3` 진입 조건

- `pytest` 통과
- `validate` CLI가 multi-period validation artifact와 validation matrix를 정상 기록함
- `status`에서 validation summary, matrix, backlog counts가 조회 가능함
