# PLAN — backlog

작성 기준일: 2026-08-28

Phase별 구현 순서. 계약은 같은 폴더의 `SPEC.md`, 근거는 `DECISIONS.md`.
참조 구현: `d:\projects\vibe-coding-claude\day4\workflow-hub\` (`tools/backlog.mjs` + `src/*.mjs`).

각 Phase = 브랜치 하나, 세션 하나. 분석 → 계획 → 작은 편집 → diff 검토 → 테스트.

---

## 적대적 검증 (모든 Phase 공통)

각 Phase의 `scope`·자체검증을 마친 뒤 반대 벤더 적대적 검증을 수행한다.
**절차·헤드리스 명령어·프롬프트 템플릿·기록 양식은 `ADVERSARIAL-REVIEW.md`를 따른다.**
근거는 `DECISIONS.md` D-7.

- 검토 대상 저장소 경로(`<REPO>`): `d:\projects\tools\backlog`
- Phase당 검토 CLI 실행 최대 3회 (Verification Attempt Limit)
- **필수 통과 Phase** (미해결 Critical이 있으면 다음 Phase로 진행 금지):
  Phase 1(validate + document_io), Phase 3(변경 — 안전한 저장).
  나머지 Phase도 적대적 검증은 수행하되 필수 통과 대상은 아니다.

---

## 참조 → 파이썬 매핑

| 참조 (`day4/workflow-hub`) | 파이썬 (`src/backlog/`) |
|---|---|
| `src/document-io.mjs` `readDocument` (FileReadError / DocumentParseError) | `document_io.py` — `read_document()`, 예외 `FileReadError` / `DocumentParseError` |
| `src/document-io.mjs` `writeDocument` (temp → rename) | `document_io.py` — `write_document()`, `tempfile` + `os.replace` |
| `src/validate.mjs` `validateDocument` (13 ErrorCode) | `validate.py` — `validate_document(doc) -> {valid, errors, task_count}` + `ID_PREFIX_MIXED` 추가 |
| `src/list.mjs` `filterAndSortTasks` / `validateFilters` / `renderTable` / `renderJson` | `query.py` — 동일. 정렬 키 `(prefix, num)` |
| `src/show.mjs` `findTaskById` / `renderText` / `renderJson` | `query.py` |
| `src/add.mjs` `computeNextId` / `computeCreateFields` / `buildTask` | `mutate.py` — 접두어 감지 추가 |
| `src/update.mjs` `computeFieldUpdates` / `applyUpdate` (`parseDepsValue`, `NULLABLE_FIELDS`) | `mutate.py` — `copy.deepcopy` |
| `tools/backlog.mjs` `parseArgs` + 디스패치 + `EXIT_CODES` | `cli.py` — argparse (최상위 `--file` + subparsers), `errors.py` |
| `todayDateString` (로컬 날짜) | `datetime.date.today().isoformat()` |

---

## 시작 전 준비

WinPython에 별도 설치할 것은 없다 (stdlib만). fixture는 Phase 1에서 만든다.

---

## Phase 0 — 스캐폴드 `feat/scaffold`

- `pyproject.toml` — `[project.scripts] backlog = "backlog.cli:main"`, `src/` 레이아웃
- `src/backlog/__init__.py`, `__main__.py`
- `errors.py` — 종료 코드 상수 `OK=0 DATA=1 ARGS=2 IO=3`, 예외 계층
- `cli.py` — argparse 골격: 최상위 `--file` (기본 `./backlog.json`) + 5개 subparser.
  각 핸들러는 `NotImplementedError`
- `CLAUDE.md` — SPEC §9.1 규약 블록
- `.claude/settings.local.json` — `"Bash(backlog *)"`, `"Bash(python -m backlog *)"`
- `docs/` 정리 — `SPEC.md` / `DECISIONS.md` / `PLAN.md`를 폴더 루트에서
  `docs/` 아래로 이동. `backlog.json`은 루트 유지 (SPEC §9)
- `.gitignore` — `*.egg-info/`, `__pycache__/`, `.*.tmp`

**산출물.** `python -m backlog --help`, `python -m backlog validate --help`가 동작한다.

**이유.** 인터페이스(옵션·기본값·서브커맨드 구조)를 먼저 못 박는다.

---

## Phase 1 — validate + document_io `feat/validate`

- `document_io.py`
  - `read_document(path)` — UTF-8 읽기 실패 → `FileReadError`, `json.loads` 실패 → `DocumentParseError`
  - `write_document(path, doc)` — `.{base}.{pid}-{uuid}.tmp`에 쓰고 `os.replace`. 실패 시 temp 정리
- `validate.py` — `validate_document(doc)` → `{"valid": bool, "errors": [{code, path, message}], "task_count": int}`
  - 최상위: `ROOT_NOT_OBJECT`, `$schema_version != "1"` → `SCHEMA_VERSION_INVALID`
  - `meta` / `enums` / `tasks` 존재·타입
  - task 필수 12필드, 타입, `title` 빈 문자열 → `TITLE_EMPTY`
  - `id`: `^[A-Z]{2,}-\d{3,}$` 아니면 `ID_FORMAT_INVALID`, 중복 → `DUPLICATE_ID`,
    **접두어 2종 이상 → `ID_PREFIX_MIXED`**
  - enum 위반 → `ENUM_INVALID` (status/priority/category)
  - 날짜: `meta.updated`, `done_at` → `DATE_FORMAT_INVALID`
  - `done` ⟺ `done_at` → `DONE_AT_MISMATCH`
  - Pass 2 참조 무결성: `parent`/`deps` → `REF_MISSING`, 자기참조 → `SELF_REFERENCE`,
    deps 중복 → `DUPLICATE_DEPS_ENTRY`
- `cli.py` — `validate` 연결. `read_document` 예외 → 종료 코드 3(IO) / 1(파싱)

**fixture.** `tests/fixtures/valid.json`, `invalid_refs.json`(dangling deps + self-ref),
`empty.json`(tasks 빈 배열), `mixed_prefix.json`.

**테스트 케이스.**
- 유효 문서 → `valid: True`, `task_count` 정확
- `$schema_version: 1` (숫자) → `SCHEMA_VERSION_INVALID`
- task에 `where` 누락 → `REQUIRED_FIELD_MISSING` `tasks[i].where`
- `id: "lb-1"` → `ID_FORMAT_INVALID`
- `YD-001`과 `ST-001` 혼재 → `ID_PREFIX_MIXED`
- `deps: ["BL-999"]` (없음) → `REF_MISSING`
- `status: "done"`, `done_at: null` → `DONE_AT_MISMATCH`
- 접두어 `BL-`만 있는 `backlog/backlog.json` → 통과

**마일스톤.** `python -m backlog validate --file backlog/backlog.json` → `VALID N task(s)`.
self-hosting 파일을 이제 기계 검증할 수 있다.

---

## Phase 2 — 조회 `feat/query`

- `query.py`
  - `filter_and_sort_tasks(tasks, filters)` — status/category/priority AND,
    `priority == "none"`은 `None` 매칭, 정렬 `(prefix, num)` (형식 불량 id는 뒤로)
  - `validate_filters(filters, enums)` — enum 대조, best-effort (enum 없으면 skip)
  - `render_table(tasks)` / `render_tasks_json(tasks)` — 마지막 열(TITLE) 자르지 않음
  - `find_task_by_id(tasks, id)`
  - `render_text(task)` / `render_task_json(task)` — 고정 필드 순서, `(none)` 처리
- `cli.py` — `list`, `show` 연결. `--format` 검증 (table/json, text/json)

**테스트 케이스.**
- 필터 없음 → 전부, id 순
- `--status todo --category 환경` → AND
- `--priority none` → priority null인 것만
- `--status bogus` → 종료 코드 1 (enum 위반)
- 빈 결과 → 헤더만, 종료 코드 0
- `--format json` 출력 → `json.loads` 성공
- `show BL-001` → 전체 필드, `show BL-999` → 종료 코드 1

---

## Phase 3 — 변경 `feat/mutate`

- `mutate.py`
  - `parse_deps_value(raw)` — trim, `"" | "none"` → `[]`, 콤마 분리
  - `NULLABLE_FIELDS = ["priority","summary","where","doc","note","parent"]`
  - `UPDATABLE_FIELDS = [...위 + "status","category","title","deps"]`
  - `detect_prefix(tasks)` — 형식 유효 id들의 접두어. 0개 → None, 2종 이상 → 오류
  - `compute_next_id(tasks, prefix)` — 해당 접두어 최대 번호 + 1, `f"{prefix}-{n:03d}"`
  - `compute_create_fields(opts)` — `title`/`category` 필수, `none`→None, deps 파싱
  - `build_task(doc, fields, today)` — 기본값 채워 append, `meta.updated` 갱신
  - `compute_field_updates(opts)` — 최소 1개, `none`→None, deps 파싱
  - `apply_update(doc, id, updates, today)` — `deepcopy`, `Object.assign` 상당,
    status 변경 시 `done_at` 자동
- `cli.py` — `add`, `update` 연결. **SPEC §6 순서**: read → parse → validate(pre) →
  mutate → validate(post) → `write_document`
  - `add`: 빈 backlog + `--prefix` 없음 → 종료 코드 2
  - `add`: `--title`/`--category` 없음 → 종료 코드 2 (IO 전)
  - `update`: 변경 옵션 0개 → 종료 코드 2 (IO 전)

**테스트 케이스.**
- `add --title X --category 환경` → `BL-00N` 출력, 파일에 append, `meta.updated` 갱신
- `add` 후 재검증 통과
- 빈 backlog `add` (`--prefix BL`) → `BL-001`
- `add --deps "BL-001,BL-002"` → 배열 저장
- `update BL-001 --status done` → `done_at` 오늘 날짜
- `update BL-001 --status todo` → `done_at` null 복귀
- `update BL-001 --parent none` → null
- `update BL-999 ...` → 종료 코드 1, 원본 불변
- `update BL-001 --deps "BL-999"` → 사후 검증 실패, 저장 안 함, 종료 코드 1
- **원자성**: 쓰기 직전 강제 실패 주입 → 원본 파일 해시 불변

---

## Phase 4 — 통합 `feat/integrate`

- `youtube_downloader/backlog.json`·`speech_transcriber/backlog.json`을
  `backlog validate`로 확인. `YD-`/`ST-` 접두어가 통과하는지, 실패하면 파일 수정
- **dogfood**: 이 도구의 `backlog/backlog.json` BL-001~BL-015를
  `python -m backlog --file backlog.json update BL-### --status done`으로 처리.
  이후 이 파일은 손 편집하지 않는다 (DECISIONS D-5)
- `README.md` — 명령, 예제 (`backlog --file ../youtube_downloader/backlog.json list --status todo`),
  종료 코드표, 단일 writer 제한
- `python -m unittest` 전체 통과, 커버리지 확인
- `backlog/`를 `d:\projects\tools\backlog\`로 옮길지 결정 (DECISIONS 미확정)

**완료 기준 (SPEC §10).**
1. 5개 명령이 명세대로 동작
2. 정상·경계·실패 테스트 존재
3. 실패한 쓰기에서 원본 byte 단위 유지
4. 세 backlog.json 전부 `validate` 통과
5. README 작성

---

## Phase 순서의 근거

- **validate가 먼저다.** 모든 쓰기 명령이 사전/사후로 validate를 호출한다.
  document_io와 validate 없이는 add/update를 못 만든다
- **조회가 변경보다 먼저다.** read-only라 위험이 없고, 렌더·필터 로직을 먼저
  안정화하면 변경 명령 테스트에서 결과 확인이 쉽다
- **self-hosting(dogfooding)은 점진적.** Phase 1부터 `validate`로 자기 점검,
  Phase 2부터 `list`/`show`로 조회, Phase 3부터 `update`로만 상태 갱신
  (그 전까지는 손 편집). DECISIONS D-5의 단계별 표 참조
