# DECISIONS — backlog

작성 기준일: 2026-08-28

파이썬 기반 과제 관리 CLI `backlog`의 설계 결정과 **그 이유**. 자기완결적이다.
계약은 같은 폴더의 `SPEC.md`.

참조 구현: `d:\projects\vibe-coding-claude\day4\workflow-hub\`
(`tools/backlog.mjs` + `src/*.mjs`) 및 그 `docs`의 명세.

---

## D-1. 기존 JS `backlog-cli` 대신 파이썬 stdlib로 포팅한다

**결정.** Node/ESM 기반 `backlog.mjs`를 쓰지 않고, 같은 기능을 파이썬 표준
라이브러리만으로 다시 작성한다.

**이유.**

- 이 워크스페이스의 다른 도구(`youtube_downloader`, `speech_transcriber`)가 전부
  파이썬(WinPython 3.11.8)이다. 과제 관리 도구까지 파이썬이면 런타임이 하나로 통일된다
- Node 22 의존이 사라진다. `d:\projects\tools\` 계열 도구는 파이썬으로 맞춘다
- 기능이 작아(검증·조회·추가·수정) 외부 패키지 없이 `argparse` + `json`으로 충분하다

**따름정리.** `pathlib` 대신 `os.path` (CLAUDE.md 규약), venv 없이 베이스 WinPython에
설치, 외부 패키지 금지.

---

## D-2. task ID 접두어를 파일별로 자동 감지한다

**결정.** 참조 구현이 `LB-###`로 하드코딩한 것을 `^[A-Z]{2,}-\d{3,}$`로 완화한다.
한 파일 안의 task는 같은 접두어를 쓴다. `add`는 그 파일의 기존 접두어를 이어쓴다.

**이유.**

- 도구별 backlog가 이미 `YD-###`(youtube_downloader), `ST-###`(speech_transcriber)를
  쓴다. `LB-`로 강제하면 이 파일들을 재번호해야 하고, 목록·상세에서 어느 도구의
  작업인지 접두어로 구분할 수 없게 된다
- 파일이 분리돼 있으므로 접두어 충돌 위험이 없다. 파일 하나 = 접두어 하나

**세부.**

- `validate`: ID는 `^[A-Z]{2,}-\d{3,}$` 형식 + 유일성만 검사한다 (참조와 동일 수준).
  한 파일에 접두어가 섞이면 `ID_PREFIX_MIXED` 오류
- `add`: 기존 task들의 접두어를 감지해 다음 번호를 붙인다. 빈 backlog는 `--prefix`
  필수 (감지할 대상이 없으므로)
- `list`: 정렬은 `(접두어, 번호)` 오름차순

---

## D-3. 참조 5개 명령을 1:1로 포팅한다

**결정.** `validate` / `list` / `show` / `add` / `update`만 만든다.
동작·옵션·종료 코드를 참조와 동일하게 유지한다.

**이유.**

- 참조 명세가 이미 검증된 계약이다. 임의로 바꾸면 참조 테스트·문서를 못 쓴다
- `delete`는 참조에서도 범위 밖이다 (ID 재사용 방지, 참조 무결성 복잡도)
- `next`(다음 할 일 추천) 같은 편의 명령은 나중에 필요가 확인되면 추가한다.
  지금은 `list --status todo`로 충분하다

**종료 코드.** `0` 성공 / `1` 데이터·검증·존재 오류 / `2` 잘못된 인자 /
`3` 파일 읽기·쓰기 오류.

---

## D-4. 안전한 저장을 그대로 유지한다

**결정.** 쓰기 명령(`add`, `update`)은 참조 §6 프로토콜을 따른다:
읽기 → 파싱 → **전체 검증** → 메모리 복제·변경 → **전체 재검증** →
2칸 들여쓰기 + 끝 개행으로 직렬화 → 같은 디렉터리 임시 파일에 쓰기 →
`os.replace()`로 원본 위치에 원자적 rename.

**이유.**

- `backlog.json`은 작업 SSOT다. 부분 쓰기나 검증 누락으로 손상되면 복구가 어렵다
- 사전 검증: 이미 깨진 파일에 변경을 얹지 않는다
- 사후 재검증: 이번 변경이 무결성을 깨면(예: 없는 deps 참조) 저장하지 않는다
- 원자적 rename: 쓰다가 죽어도 원본이 byte 단위로 남는다
- `os.replace`는 Windows에서도 같은 볼륨이면 원자적이다

**한계 (참조와 동일).** 단일 writer 가정. 여러 프로세스 동시 쓰기·파일 잠금은 범위 밖.

---

## D-5. 이 도구도 자체 backlog.json으로 관리한다 (self-hosting)

**결정.** `backlog/backlog.json`에 이 CLI 자체의 구현 작업(`BL-###`)을 같은 포맷으로
담고, CLI가 준비되는 대로 이 파일도 CLI로 관리한다 (dogfooding).

**이유.** 포맷과 명령이 실제로 쓸 만한지 스스로 검증한다.

**단계별 관리 방식.**

| 시점 | `backlog/backlog.json` 관리 |
|---|---|
| Phase 0~2 | CLI 미완성 — 손으로 편집 (부트스트랩 예외) |
| Phase 1 이후 | `python -m backlog validate --file backlog.json`으로 자기 검증 |
| Phase 2 이후 | `... list` / `... show`로 조회 |
| **Phase 3 이후** | `... update BL-### --status ...`로만 상태 갱신 (손 편집 중단) |
| Phase 4 | BL-001~BL-015를 CLI `update`로 `done` 처리하며 dogfood 확인 |

접두어는 `BL-`. 이 파일이 비어 있지 않으므로 `add` 시 `--prefix` 불필요.

---

## D-6. hook / MCP는 이 도구가 만들지 않는다

**결정.**

- 참조의 `backlog-json-guard.mjs`(PreToolUse에서 `backlog.json` Read/Edit/Write
  차단)는 포팅하지 않는다. CLI를 먼저 완성한다.
- 참조의 `mcp/server.mjs`(validate/list를 MCP 도구로 노출)도 만들지 않는다.

**이유.**

- **hook은 소비 측 관심사다.** `backlog.json`을 손대지 못하게 막는 것은 그 파일이
  있는 워크스페이스(`youtube_downloader/`, `speech_transcriber/`, 그리고 이 폴더)의
  `.claude/hooks/` 설정이지, `backlog` 도구의 코드가 아니다. 필요해지면 각
  워크스페이스에 **파이썬 PreToolUse hook**으로 추가한다 (참조는 Node 구현이라
  이식 필요). 우선순위 낮음
- **MCP는 이 도구군 방침상 안 만든다** (상위 설계 결정). 결정론적 배치 CLI라
  모델이 인자를 고를 일이 없고, Claude Code가 Bash로 실행하면 된다.
  참조가 MCP를 둔 것은 학습용 예시일 뿐

**참조 hook 이식 시 메모** (나중에 만들 때):
`.claude/hooks/backlog_json_guard.py` — stdin의 PreToolUse JSON을 읽어
`tool_input.file_path`가 그 워크스페이스의 `backlog.json`을 가리키면
`permissionDecision: "deny"` 출력. 파싱 실패 시 fail-closed(exit 2).

---

## D-7. 반대 벤더 적대적 검증

**결정.** 각 Phase 구현·자체검증 후, 마지막 실질 구현자의 **반대 벤더 CLI**에
적대적 검증을 위임한다. Phase 하나당 검토 CLI 실행은 실패·재실행·보완 후 재검증을
모두 포함해 **최대 3회**. 절차·헤드리스 명령어는 `ADVERSARIAL-REVIEW.md`,
Phase별 지정은 `PLAN.md` "적대적 검증" 절.

- Claude Code 구현 → Codex `gpt-5.6-sol` 가 검토
- Codex 구현 → Claude `opus-5` 가 검토
- 기록: `docs/reviews/A{n}.md`

**이유.** 단일 벤더 자기검증은 같은 맹점을 공유한다. 반대 벤더가 계약 위반·경계
조건·부작용을 공격하면 결함 발견율이 오른다. 무한 재검토는 비용이 크고 3회차
이후 지적이 같은 계열로 수렴하므로 상한을 둔다. `file_manager`,
`markdown_browser`와 같은 운영 방식이며 3도구 공통이다.

---

## 미확정

- `add`/`update`에서 여러 backlog 파일을 한 번에 다루는 편의 기능 (지금은 `--file` 하나씩)
- `.lock` 없이 단일 writer 가정 유지 여부

## 해소됨

- `backlog/` 위치: `d:\projects\tools\backlog\`로 확정 (Phase 4 시점 이미 이 경로에 있음)
