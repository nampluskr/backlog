# ADVERSARIAL-REVIEW — 반대 벤더 적대적 검증 절차

작성 기준일: 2026-08-28

`youtube_downloader`, `speech_transcriber`, `backlog` 세 도구 공통. 각 도구 `PLAN.md`의
"적대적 검증" 절이 이 문서를 참조한다. 결정 근거는 각 도구 `DECISIONS.md` 및
상위 `decisions.md` D-34.

이 문서는 설계 원본이 `260828_youtube-to-doc/docs/`에 있고, 각 도구 저장소로
복사되어 `docs/ADVERSARIAL-REVIEW.md`로 함께 배포된다.

---

## 절차 (모든 Phase 공통)

각 Phase의 `scope`·자체검증을 마친 뒤:

1. **반대 벤더 CLI에 위임한다.** 검토자는 마지막 실질 구현자의 반대 벤더다.
   - Claude Code 구현 → Codex `gpt-5.6-sol` 가 검토
   - Codex 구현 → Claude `opus-5` 가 검토
   - 토큰 한도로 구현자가 Phase 중간에 바뀌면 마지막 실질 구현자를 기준으로 다시 정한다.

2. **검토자 제약.** 검토자는 제품 소스 파일, 해당 Phase의 공격 초점(각 Phase 설명의
   "핵심"·"테스트 케이스"), 관련 PLAN 조항만 사용한다. 파일을 수정하지 않는다.
   구현 세션 대화·구현 판단 근거·문서·설정·실험 산출물·Git 상태/이력/원격·셸 도구는
   요청하거나 사용하지 않는다. 지적은 `Critical / Major / Minor`, 정확한 재현 조건,
   위반한 PLAN 조항을 포함해 심각도순으로 반환한다.

3. **보완.** Critical 지적은 모두 수정하고 관련 검증을 재실행한다. Major·Minor는
   처리 여부와 근거를 기록한다. Critical을 수정했으면 같은 반대 벤더 검토를 한 번 더
   실행해 해소를 확인한다.

4. **Verification Attempt Limit.** 하나의 검증 대상(Phase 1개 또는 문서 1개)에 대한
   검토 CLI 실행은 **실패·오류·프롬프트 재작성·보완 후 재검증을 모두 포함해 최대 3회**로
   제한한다. 보완 사이클을 별도로 세지 않는다. 3회를 소진하면 추가 실행 대신 마지막
   유효 검토 결과, 반영한 보완, 미해결 지적과 남은 위험을 기록하고 사용자에게 보고한다.
   3회 소진 시점에 미해결 Critical이 남아 있으면 다음 Phase로 진행하지 않고 사용자
   판단을 요청한다.

5. **기록.** `docs/reviews/A{n}.md`에 구현자, 검토 모델, 대상 파일, 실행 일시,
   회차별 결과(유효 여부·사유), 심각도별 건수, 지적·재현 조건·관련 PLAN 조항·처리
   상태를 기록한다. 유효하지 않은 지적의 반박 근거도 남긴다.

6. **CLI 부재 시.** 필요한 반대 벤더 CLI를 사용할 수 없으면 오류와 대체 검증안을
   사용자에게 보고하고, 승인 없이 생략하지 않는다.

**필수 통과 Phase**(미해결 Critical이 있으면 다음 Phase로 진행 금지)는 각 도구
`PLAN.md`의 "적대적 검증" 절에서 지정한다. 나머지 Phase도 적대적 검증은 수행하되
필수 통과 대상은 아니다.

---

## 헤드리스 명령어

`<REPO>` = 검토 대상 저장소의 절대 경로 (예: `d:\projects\tools\youtube_downloader`).
`<PROMPT>` = 아래 프롬프트 템플릿을 치환한 문자열.

### Codex 검토 (Claude Code 구현 대상)

```
codex.cmd exec --model gpt-5.6-sol --sandbox read-only --cd "<REPO>" "<PROMPT>"
```

### Claude 검토 (Codex 구현 대상)

```
claude -p "<PROMPT>" --model opus --safe-mode --allowedTools "Read,Glob,Grep" --disallowedTools "Edit,Write,Bash" --permission-mode dontAsk --max-turns 5 --output-format json --no-session-persistence
```

- 모델 접근이 거부되면 기본 모델로 조용히 폴백하지 않고 오류와 대체안을 보고한다.
- 검토 CLI 실행 시간 제한은 기본 10분. 필요 시 `--max-budget-usd`로 호출별 비용 상한.
- 문서 검증 시에는 검토자가 상위 문서·`AGENTS.md`를 읽도록 읽기 전용 셸
  (`cat`, `sed -n`)만 허용한다.

---

## 프롬프트 템플릿

`<Phase>`·`<changed-files>`·`<adversarial-focus>`·`<plan-refs>` 를 현재 작업 내용으로 치환한다.

```
You are an adversarial reviewer for <Phase>. Your job is to break this code, not to confirm it works. Review only these product source files: <changed-files>. Attack these specific points: <adversarial-focus>. Validate against these PLAN clauses: <plan-refs>. Do not inspect Git status, branches, remotes, or commit history, and do not use shell tools. For each finding, report severity (Critical/Major/Minor), exact reproduction conditions, and the violated PLAN clause. Order findings by severity. Do not modify any file.
```

---

## 검토 기록 양식 (`docs/reviews/A{n}.md`)

```
# A{n} — <도구> Phase <n> 적대적 검증

- 구현자: Claude Code | Codex
- 검토 모델: gpt-5.6-sol | opus-5
- 대상 파일: ...
- 관련 PLAN 조항: ...
- 실행 회차: 1/3, 2/3, ... (각 회차: 일시, 유효 여부, 사유)

## 지적

| # | 심각도 | 요약 | 재현 조건 | 위반 조항 | 처리 |
|---|---|---|---|---|---|

## 유효하지 않은 지적과 반박 근거

## 미해결 · 남은 위험
```
