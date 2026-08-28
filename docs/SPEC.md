# SPEC — backlog

작성 기준일: 2026-08-28

`backlog.json`을 프로젝트 작업의 단일 진실 공급원(SSOT)으로 다루는 파이썬 CLI.
`validate` / `list` / `show` / `add` / `update` 다섯 명령을 제공한다.

이 문서는 자기완결적이다. 설계 근거는 같은 폴더의 `DECISIONS.md`.
참조 구현(Node/ESM)은 `d:\projects\vibe-coding-claude\day4\workflow-hub\` —
이 SPEC는 그 명세를 파이썬판으로 옮긴 것이며 데이터 계약·종료 코드는 동일하다.

---

## 1. 목적

사용자(또는 에이전트)는 `backlog` CLI로 작업 데이터를 검증하고, 목록·상세를
조회하고, 작업을 추가하고, 기존 작업을 수정한다. `backlog.json`을 손으로 편집하지
않고 이 CLI로만 다룬다 (사전/사후 검증과 원자적 저장을 우회하지 않기 위함).

이 도구 자신의 `backlog/backlog.json`도 CLI가 준비되는 대로 CLI로 관리한다
(dogfooding). 부트스트랩 단계(Phase 0~2)의 손 편집 예외는 `DECISIONS.md` D-5 참조.

---

## 2. 실행 환경

| 항목 | 값 |
|---|---|
| 파이썬 | WinPython 3.11.8 — `C:\winpython\WPy64-31180\python-3.11.8.amd64\python.exe` |
| 격리 | venv 없이 베이스 WinPython에 설치 |
| 의존성 | **표준 라이브러리만** (`argparse`, `json`, `os`, `sys`, `copy`, `tempfile`, `datetime`, `re`) |
| 테스트 | `unittest` (stdlib) |
| 경로 | `os.path` 사용, `pathlib` 금지 |

---

## 2.1 소비 워크스페이스에서 사용하기

`youtube_downloader/`, `speech_transcriber/`, 그리고 이 폴더처럼 자체
`backlog.json`을 두는 워크스페이스에서 이 CLI를 쓰는 방법. **MCP를 쓰지 않는다**
(§8, `DECISIONS.md` D-6) — Claude Code가 Bash로 직접 실행한다.

### 설치 (1회, 전역)

```
C:\winpython\WPy64-31180\python-3.11.8.amd64\python.exe -m pip install -e <backlog 폴더 경로>
```

`[project.scripts]` 덕분에 WinPython `Scripts\`에 `backlog.exe`가 생기고,
이후 **어느 디렉터리에서든** `backlog ...`로 실행된다. 워크스페이스별 설치는 없다.
(설치 전이면 `python -m backlog ...`도 동일하게 동작한다.)

### 실행

`--file`은 현재 작업 디렉터리 기준 상대경로다. 각 워크스페이스에서 자기
`backlog.json`을 가리킨다.

```bash
# youtube_downloader/ 에서 작업 중
backlog --file backlog.json list --status todo
backlog --file backlog.json show YD-020
backlog --file backlog.json update YD-020 --status in_progress
backlog --file backlog.json update YD-020 --status done

# speech_transcriber/ 에서
backlog --file backlog.json list --category whisper --format json
```

### 권한 설정 (프롬프트 없이 쓰려면)

각 워크스페이스의 `.claude/settings.local.json`:

```json
{ "permissions": { "allow": ["Bash(backlog *)"] } }
```

### CLAUDE.md 규약 (각 워크스페이스에 넣을 한 줄)

```
- backlog.json 은 직접 편집하지 말고 backlog CLI 로만 다룬다
  (backlog --file backlog.json <validate|list|show|add|update>)
```

---

## 3. 명령

```
backlog [--file PATH] validate
backlog [--file PATH] list [--status V] [--priority V|none] [--category V] [--format table|json]
backlog [--file PATH] show <id> [--format text|json]
backlog [--file PATH] add --title T --category C [옵션...] [--prefix PREFIX]
backlog [--file PATH] update <id> <변경옵션 1개 이상>
```

- `--file`은 최상위 옵션이며 서브커맨드 **앞**에 온다. 생략 시 `./backlog.json`
- 진입점: `python -m backlog ...` 또는 설치 시 `backlog ...`
  (`pyproject.toml`의 `[project.scripts] backlog = "backlog.cli:main"`)
- nullable 필드에 넘긴 `none`(문자열)은 JSON `null`로 저장된다
- stdout = 정상 결과, stderr = 오류. 오류 출력에 트레이스백을 넣지 않는다

### add / update 옵션

| 옵션 | add | update | 비고 |
|---|---|---|---|
| `--title` | 필수 | 가능 | 비어 있지 않은 문자열 |
| `--category` | 필수 | 가능 | `enums.category` 값 |
| `--status` | 선택(기본 `todo`) | 가능 | `enums.status` 값 |
| `--priority` | 선택(기본 `null`) | 가능 | `enums.priority` 값 또는 `none` |
| `--summary` `--where` `--doc` `--note` `--parent` | 선택 | 가능 | 문자열 또는 `none` |
| `--deps` | 선택(기본 `[]`) | 가능 | 콤마 구분 ID 목록. `""` 또는 `none` → `[]` |
| `--prefix` | 빈 backlog일 때만 필수 | — | 새 ID 접두어 (예: `BL`) |

- `update`는 변경 옵션이 **최소 1개** 있어야 한다
- `update`로 바꿀 수 없는 것: `id`, `$schema_version`, `enums`, `done_at` (자동 처리)

---

## 4. 데이터 계약

### 최상위 구조

- `$schema_version`: 문자열 `"1"`
- `meta`: 객체
- `enums`: 객체
- `tasks`: 배열

### meta

- `updated`: `YYYY-MM-DD` 날짜 문자열 (성공한 `add`/`update`가 실행 날짜로 갱신)
- `context_doc`: 문자열 또는 `null`
- `note`: 문자열 또는 `null`

### enums

- `status`, `priority`, `category`는 각각 배열
- 명령의 허용값은 **현재 파일의 enum에서** 읽는다. 코드에 하드코딩하지 않는다

### task (모든 필드 필수)

| 필드 | 규칙 |
|---|---|
| `id` | `^[A-Z]{2,}-\d{3,}$`. 유일. 생성 후 수정 불가. **한 파일은 접두어 하나** |
| `status` | `enums.status`에 포함 |
| `priority` | `enums.priority`에 포함 또는 `null` |
| `category` | `enums.category`에 포함 |
| `title` | 비어 있지 않은 문자열 |
| `summary` `where` `doc` `note` | 문자열 또는 `null` |
| `parent` | 기존의 다른 task ID 또는 `null` |
| `deps` | 기존의 다른 task ID 배열 (중복 불가) |
| `done_at` | `YYYY-MM-DD` 또는 `null` |

### 참조 무결성

- ID 중복 금지
- `parent`·`deps`는 존재하는 task만 참조
- 자기 자신을 `parent`·`deps`로 참조 금지
- `deps` 내 같은 ID 중복 금지

### 상태와 날짜

- 새 작업 기본 상태 `todo`
- 상태를 `done`으로 바꾸면 `done_at`을 실행 날짜로 설정 (이미 있으면 덮어쓰지 않음)
- `done`에서 다른 상태로 바꾸면 `done_at`을 `null`로
- `status: "done"` ⟺ `done_at` non-null (`validate`가 검사)

---

## 5. 명령별 동작

### validate

JSON 문법, `$schema_version`, 필수 필드, 타입, enum, ID 형식·유일성·접두어 일관,
참조 무결성, `done_at` 정합을 검사한다. 데이터를 바꾸지 않는다.

- 유효: stdout에 `VALID <n> task(s)`, 종료 코드 0
- 무효: stderr에 `INVALID: <n> problem(s) found in '<file>'` + `  - <path>: <message> [<CODE>]` 목록, 종료 코드 1

**ErrorCode** (참조와 동일 + 1개 추가):
`ROOT_NOT_OBJECT` `SCHEMA_VERSION_INVALID` `REQUIRED_FIELD_MISSING` `TYPE_MISMATCH`
`DATE_FORMAT_INVALID` `ENUM_INVALID` `ID_FORMAT_INVALID` `DUPLICATE_ID` `TITLE_EMPTY`
`REF_MISSING` `SELF_REFERENCE` `DUPLICATE_DEPS_ENTRY` `DONE_AT_MISMATCH`
`ID_PREFIX_MIXED`(추가)

### list

- 기본 정렬: `(접두어, 번호)` 오름차순
- `--status` `--priority` `--category` 필터는 AND 결합. 각 생략 시 no-op
- `--priority none`은 `priority == null`인 작업과 매칭
- 필터 값은 파일의 enum과 대조 (`none` 제외). 어긋나면 종료 코드 1
- 결과 없어도 정상 (헤더만 출력, 종료 코드 0)
- `--format table`(기본): 공백 정렬 표 `ID STATUS PRIORITY CATEGORY TITLE`, TITLE은 자르지 않음
- `--format json`: `json.loads`로 되읽을 수 있는 배열
- 데이터를 바꾸지 않는다

### show

- `<id>` 한 작업의 전체 필드를 고정 순서로 출력
  (`id status priority category title summary where parent deps doc done_at note`)
- `--format text`(기본): `field: value` 줄. `null`·빈 deps는 `(none)`, deps는 콤마 결합
- `--format json`: 단일 객체
- ID 없으면 stderr에 `Error: no task with id "<id>"`, 종료 코드 1
- 데이터를 바꾸지 않는다

### add

- `--title`·`--category` 필수 (없으면 종료 코드 2, 파일 IO 전에)
- 접두어 감지: 기존 task들의 공통 접두어. 빈 backlog면 `--prefix` 필수
- 다음 ID = 해당 접두어의 최대 번호 + 1, 최소 3자리 zero-pad (`BL-007` → `BL-008`,
  `BL-999` → `BL-1000`). 삭제된 번호 재사용 안 함
- 기본값: `status: "todo"`, `priority: null`, `parent: null`, `deps: []`,
  `done_at: null`, 나머지 nullable은 `null`
- 성공 시 stdout에 생성한 ID, 종료 코드 0

### update

- 변경 옵션 1개 이상 필요 (없으면 종료 코드 2, 파일 IO 전에)
- 없는 작업 / 허용 안 된 enum / 잘못된 참조 → 원본 불변, 종료 코드 1
- 성공 시 stdout에 `Updated <id>`, 종료 코드 0

---

## 6. 안전한 저장

쓰기 명령(`add`, `update`)은 다음 순서를 지킨다.

1. 원본을 UTF-8로 읽는다
2. `json.loads` 한다
3. **현재 문서 전체를 검증한다** (이미 무효면 중단, 종료 코드 1)
4. `copy.deepcopy`로 복제하고 변경한다
5. **변경 후 전체를 다시 검증한다** (무효면 중단, 저장 안 함, 종료 코드 1)
6. 2칸 들여쓰기 + 파일 끝 개행 한 줄로 직렬화한다
   (`json.dumps(doc, ensure_ascii=False, indent=2) + "\n"`)
7. 같은 디렉터리의 고유 임시 파일(`.{name}.{pid}-{uuid}.tmp`)에 쓴다
8. `os.replace(tmp, path)`로 원본 경로에 원자적 rename 한다

- 실패하면 원본을 삭제하거나 덮어쓰지 않는다. 임시 파일은 best-effort 정리
- 단일 writer 가정. 동시 쓰기 잠금은 범위 밖

---

## 7. 종료 코드

| 코드 | 의미 |
|---|---|
| 0 | 성공 |
| 1 | JSON·데이터·검증·존재 여부 오류 |
| 2 | 잘못된 명령, 누락·알 수 없는 옵션 |
| 3 | 파일 읽기·쓰기 오류 |

정상 결과는 stdout, 오류는 stderr. 오류 출력에 트레이스백을 포함하지 않는다.

---

## 8. 범위 밖

- 작업 삭제
- 원격 서버·DB 동기화
- 여러 프로세스 동시 쓰기·파일 잠금
- 임의의 범용 JSON 편집
- 외부 파이썬 패키지
- **MCP 서버.** 참조 구현(`mcp/server.mjs`)은 validate/list를 MCP 도구로
  노출하지만 만들지 않는다. 이 도구군은 MCP를 쓰지 않기로 했다 (상위 설계 결정).
  결정론적 CLI라 Claude Code가 Bash로 직접 실행하면 충분하다
- backlog.json 직접 편집 차단 hook (DECISIONS D-6 — 나중에, 소비 워크스페이스 쪽)

---

## 9. 저장소 폴더 구조

독립 워크스페이스. `youtube_downloader/`, `speech_transcriber/`와 같은 배치.

```
backlog/
    .claude/
        settings.local.json    # 권한 허용목록 — "Bash(backlog *)" 등
    docs/
        SPEC.md                # 이 문서
        DECISIONS.md
        PLAN.md
    backlog.json               # 이 도구 자체의 작업 SSOT (접두어 BL-, self-hosting)
    src/
        backlog/
            __init__.py
            __main__.py        # python -m backlog
            cli.py             # argparse (최상위 --file + subparsers), 디스패치, main()
            errors.py          # 종료 코드 상수, 예외 계층
            document_io.py     # 읽기(에러 2종 구분), 원자적 쓰기
            validate.py        # 전 검증 규칙 → {valid, errors, task_count}
            query.py           # list 필터·정렬·렌더, show 조회·렌더
            mutate.py          # add(접두어 감지·다음 ID), update(none→null·deps·done_at)
    tests/
        __init__.py
        fixtures/
            valid.json
            invalid_refs.json  # dangling deps + self-reference
            empty.json         # tasks 빈 배열
            mixed_prefix.json  # 접두어 2종 혼재 (ID_PREFIX_MIXED)
        test_validate.py
        test_query.py
        test_mutate.py
        test_document_io.py
        test_cli.py
    CLAUDE.md                  # 작성 규약 (§9.1)
    README.md                  # 명령, 예제, 종료 코드표, 단일 writer 제한
    pyproject.toml             # [project.scripts] backlog = "backlog.cli:main"
    .gitignore
```

**현재 위치**: 이 워크스페이스(`260828_youtube-to-doc/backlog/`)에서는 `SPEC.md` /
`DECISIONS.md` / `PLAN.md`가 폴더 루트에 평면 배치되어 있다. `d:\projects\tools\backlog\`로
옮길 때 이 셋을 `docs/` 아래로 정리한다. `backlog.json`은 루트에 그대로 둔다
(`--file backlog.json`으로 자주 접근).

### 9.1 CLAUDE.md에 넣을 규약

```
- 작업 시작 전 docs/SPEC.md 와 docs/DECISIONS.md 를 읽을 것
- 경로는 os.path 사용, pathlib 금지
- 표준 라이브러리만. 외부 패키지 금지
- 타입 힌트와 docstring 은 요청 시에만
- 코드 내 주석은 영어
- 명시적 인자 전달, **kwargs 지양
- 대입문의 수직 정렬 금지
- 모든 쓰기는 사전/사후 전체 검증 + 임시파일 후 os.replace (SPEC §6)
- 이 도구 자신의 backlog.json 도 Phase 3 이후엔 backlog CLI 로만 수정
- 테스트는 fixture 임시 복사본만 수정한다
```

Phase별 착수 순서는 `PLAN.md`에서 다룬다.

---

## 10. 완료 조건

- `validate` `list` `show` `add` `update`가 이 명세대로 동작한다
- 정상·경계·실패 테스트가 있다 (`python -m unittest`)
- 실패한 쓰기 명령에서 원본이 byte 단위로 유지된다
- `youtube_downloader/backlog.json`·`speech_transcriber/backlog.json`·
  `backlog/backlog.json`이 `backlog validate`를 통과한다
- `README.md`에 명령, 예제, 종료 코드, 단일 writer 제한을 기록한다
