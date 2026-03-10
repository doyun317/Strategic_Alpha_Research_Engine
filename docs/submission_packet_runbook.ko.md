# Submission Packet Runbook

## 1. 목적

이 문서는 `autopilot` 실행 후 생성된 submission packet을
로컬 artifact/state ledger 기준으로 검토하기 위한 runbook이다.

## 2. 전제 조건

아래가 이미 준비되어 있어야 한다.

1. `autopilot` 실행으로 candidate 탐색과 packet 생성이 끝나 있음
2. `.venv`와 개발 의존성이 설치되어 있음
3. `state/latest_submission_manifest.json` 이 생성되어 있음

## 3. 기본 실행 순서

```bash
ART=artifacts

python -m strategic_alpha_engine autopilot --artifacts-dir "$ART" --brain-provider fake
python -m strategic_alpha_engine status --artifacts-dir "$ART"
cat "$ART/state/latest_submission_manifest.json"
```

실제 운영 경로는 provider만 바꾸면 된다.

```bash
python -m strategic_alpha_engine autopilot --artifacts-dir "$ART" --brain-provider worldquant
```

## 4. 생성되는 산출물

`autopilot` 실행이 성공하면 아래가 생성된다.

```text
artifacts/
  runs/
    <autopilot_run_id>/
      autopilot_manifest.json
      auto_review.jsonl
    <packet_run_id>/
      agenda.json
      hypothesis.json
      blueprint.json
      submission_packets.jsonl
      packets/
        <candidate_id>.json
  state/
    latest_submission_manifest.json
    submission_packet_index.jsonl
```

`submission_packets.jsonl`은 run 전체 요약용이고,
`packets/<candidate_id>.json`은 개별 제출 packet 확인용이다.

## 5. Packet 내용

각 packet은 아래 lineage를 self-contained하게 포함한다.

1. agenda / hypothesis / blueprint
2. candidate + static validation + critique
3. simulation request / run / result
4. Stage A evaluation / promotion
5. Stage B/C validation summary와 원본 validation record
6. synthetic submission-ready 승격
7. synthetic auto-review decision

즉 packet 하나만 열어도 후보가 어떤 근거로 여기까지 왔는지 재구성할 수 있어야 한다.

## 6. 상태 확인 포인트

`status`에서 아래를 확인한다.

1. `autopilot_status.latest_run_id`
2. `latest_submission_manifest.selected_packet_count`
3. `submission_packet_summary.total_packets`
4. `submission_packet_index.unique_signatures`

## 7. 운영 주의사항

1. packet에는 hypothesis, blueprint, validation rationale, review note가 함께 들어가므로 외부 공유 전에 민감도 검토가 필요하다.
2. packet 생성 기준은 `autopilot` 안의 selection policy와 cumulative signature dedupe 규칙을 따른다.
3. 제출 후보는 항상 `state/latest_submission_manifest.json`을 기준으로 검토한다.
