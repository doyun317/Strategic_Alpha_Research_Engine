# Submission Packet Runbook

## 1. 목적

이 문서는 `submission_ready -> human review -> submission packet` 흐름을
로컬 artifact/state ledger 기준으로 반복 가능하게 실행하기 위한 runbook이다.

## 2. 전제 조건

아래가 이미 준비되어 있어야 한다.

1. `simulate` 실행으로 Stage A 결과가 저장되어 있음
2. `validate` 실행으로 multi-period validation 결과가 저장되어 있음
3. `promote` 실행으로 `submission_ready` 후보가 생성되어 있음
4. `.venv`와 개발 의존성이 설치되어 있음

## 3. 기본 실행 순서

```bash
python -m strategic_alpha_engine simulate --artifacts-dir artifacts
python -m strategic_alpha_engine validate --artifacts-dir artifacts
python -m strategic_alpha_engine promote --artifacts-dir artifacts
python -m strategic_alpha_engine review --artifacts-dir artifacts --decision approve
python -m strategic_alpha_engine packet --artifacts-dir artifacts
python -m strategic_alpha_engine status --artifacts-dir artifacts
```

특정 review run만 대상으로 packet을 만들고 싶으면:

```bash
python -m strategic_alpha_engine packet \
  --artifacts-dir artifacts \
  --source-run-id review.quality_deterioration.20260309T120000000000Z
```

특정 candidate만 packet으로 묶고 싶으면:

```bash
python -m strategic_alpha_engine packet \
  --artifacts-dir artifacts \
  --source-run-id review.quality_deterioration.20260309T120000000000Z \
  --candidate-id cand.bp.quality_deterioration.001.001
```

## 4. 생성되는 산출물

`packet` 실행이 성공하면 아래가 생성된다.

```text
artifacts/
  runs/
    <packet_run_id>/
      agenda.json
      hypothesis.json
      blueprint.json
      submission_packets.jsonl
      packets/
        <candidate_id>.json
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
6. submission-ready promotion
7. human review decision

즉 packet 하나만 열어도 후보가 어떤 근거로 여기까지 왔는지 재구성할 수 있어야 한다.

## 6. 상태 확인 포인트

`status`에서 아래를 확인한다.

1. `runs.counts_by_kind.packet`
2. `submission_packet_summary.latest_run_id`
3. `submission_packet_summary.total_packets`
4. `submission_packet_summary.candidate_ids`

## 7. 운영 주의사항

1. packet에는 hypothesis, blueprint, validation rationale, review note가 함께 들어가므로 외부 공유 전에 민감도 검토가 필요하다.
2. `packet`은 최신 상태가 `submission_ready`이고 latest review queue 상태가 `approved`인 후보만 대상으로 한다.
3. review 이후 후보가 `hold` 또는 `reject`로 바뀌면 이전 approve run을 지정해도 packet 대상에서 제외된다.
