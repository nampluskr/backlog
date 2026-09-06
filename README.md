# backlog

`backlog.json`을 프로젝트 작업의 단일 진실 공급원(SSOT)으로 다루는 파이썬 CLI.
`validate` / `list` / `show` / `add` / `update` 다섯 명령. 표준 라이브러리만 사용.

기존 Node/ESM 참조 구현(`d:\projects\vibe-coding-claude\day4\workflow-hub`)의
다섯 명령을 파이썬으로 옮긴 것이다. task 구조와 종료 코드 체계는 대체로 참조를 따르되
아래 의도된 차이가 있다: task ID 접두어를 파일별로 자동 감지하고(참조는 `LB-` 고정),
그에 따라 `ID_PREFIX_MIXED` 검증 규칙을 추가했으며, 참조의 hook·MCP 서버는 포팅하지 않았다
(`docs/DECISIONS.md` D-2, D-6). 데이터 계약은 `docs/SPEC.md`, 설계 근거는
`docs/DECISIONS.md`, Phase별 착수 순서는 `docs/PLAN.md`.

## 상태

**Phase 4 완료.** 다섯 명령이 명세대로 동작하고, 세 `backlog.json`
(`backlog` / `youtube_downloader` / `speech_transcriber`)이 모두 `validate`를 통과한다
(각각 16 / 19 / 19 task). 테스트 96개 통과. Phase 1~4 반대 벤더 적대적 검증 기록은
`docs/reviews/` (A1~A4). Phase 0(스캐폴드)은 별도 적대적 검증 기록이 없다.

`backlog.json`은 이제 손 편집하지 않고 CLI로만 관리한다 (dogfooding, DECISIONS D-5).

## 설치

WinPython(3.11.8)에 venv 없이 전역 설치한다. 표준 라이브러리만 쓰므로 추가 의존성은 없다.

```
C:\winpython\WPy64-31180_cpu\python-3.11.8.amd64\python.exe -m pip install -e .
```

`[project.scripts]` 덕분에 WinPython `Scripts\` 폴더
(`C:\winpython\WPy64-31180_cpu\python-3.11.8.amd64\Scripts`)에 `backlog.exe`가 생긴다.
이 폴더가 `PATH`에 있으면 어느 디렉터리에서든 `backlog ...`로, 없으면
`...\Scripts\backlog.exe ...` 또는 위 인터프리터로 `-m backlog ...`로 실행한다.
설치하지 않고 쓰려면 `$env:PYTHONPATH="src"` 설정 후 위 인터프리터로 `-m backlog ...`
(맨 `python` 금지 — `docs/SPEC.md` §2).

## 명령

```
backlog [--file PATH] validate
backlog [--file PATH] list [--status V] [--priority V|none] [--category V] [--format table|json]
backlog [--file PATH] show <id> [--format text|json]
backlog [--file PATH] add --title T --category C [--status S] [--priority P|none]
                          [--summary ..] [--where ..] [--doc ..] [--note ..]
                          [--parent ID|none] [--deps "ID,ID"] [--prefix PREFIX]
backlog [--file PATH] update <id> <변경 옵션 1개 이상>
```

- `--file`은 최상위 옵션이며 서브커맨드 **앞**에 온다. 생략 시 현재 디렉터리의 `./backlog.json`
- nullable 필드에 넘긴 문자열 `none`은 JSON `null`로 저장된다
- `--deps`는 콤마 구분. `""` 또는 `none`이면 `[]`
- `update`로 바꿀 수 없는 것: `id`, `$schema_version`, `enums`, `done_at`(자동)
- 정상 결과는 stdout, 오류는 stderr. 오류 출력에 트레이스백을 넣지 않는다
- 성공한 `add`/`update`는 `meta.updated`를 실행 날짜로 갱신한다
- `status`를 `done`으로 바꾸면 `done_at`이 실행 날짜로 채워지고, `done`에서
  벗어나면 `null`로 되돌아간다

## 예제

```bash
# 이 도구 자신의 backlog
backlog --file backlog.json validate
backlog --file backlog.json list --status todo
backlog --file backlog.json show BL-016

# 소비 워크스페이스 (접두어는 파일에서 자동 감지)
backlog --file ../youtube_downloader/backlog.json list --status todo
backlog --file ../youtube_downloader/backlog.json update YD-020 --status in_progress
backlog --file ../speech_transcriber/backlog.json list --category whisper --format json

# 새 작업 추가 / 수정
backlog --file backlog.json add --title "새 작업" --category 통합 --deps "BL-009,BL-012"
backlog --file backlog.json update BL-016 --status done
```

`add`는 생성한 ID를, `update`는 `Updated <id>`를 stdout에 출력한다.

## 종료 코드

| 코드 | 의미 |
|---|---|
| 0 | 성공 |
| 1 | JSON·데이터·검증 오류, 없는 ID, 잘못된 필터 값 |
| 2 | 잘못된 명령, 누락·알 수 없는 옵션 (파일 IO 전에 판정) |
| 3 | 파일 읽기·쓰기 오류 |

## 안전한 저장

쓰기 명령(`add`, `update`)은 다음 순서를 지킨다 (SPEC §6).

1. 원본을 UTF-8로 읽고 `json.loads`
2. **현재 문서 전체 검증** — 이미 무효면 중단 (코드 1)
3. `copy.deepcopy` 후 메모리에서 변경
4. **변경 후 전체 재검증** — 무효면 저장하지 않고 중단 (코드 1)
5. 2칸 들여쓰기 + 끝 개행으로 직렬화
6. 같은 디렉터리의 고유 임시 파일에 쓰고 `os.replace`로 원자적 rename

실패하면 원본을 삭제·덮어쓰지 않는다. 임시 파일은 best-effort 정리.

**단일 writer 가정.** 여러 프로세스가 같은 `backlog.json`에 동시에 쓰는 경우는
범위 밖이다. 파일 잠금을 걸지 않는다.

## 테스트

```
$env:PYTHONPATH="src"
C:\winpython\WPy64-31180_cpu\python-3.11.8.amd64\python.exe -m unittest discover -s tests
```

정상·경계·실패 케이스를 `tests/`에 둔다. fixture는 임시 복사본만 수정한다.
