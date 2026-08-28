# backlog Agent Instructions

Claude Code가 이 저장소에서 작업할 때 매 턴 지켜야 하는 규칙이다.
배경과 근거는 `docs/SPEC.md`, `docs/DECISIONS.md`에 있다.
참조 구현: `d:\projects\vibe-coding-claude\day4\workflow-hub`.

## 규약

- 작업 시작 전 `docs/SPEC.md` 와 `docs/DECISIONS.md` 를 읽을 것
- 경로는 `os.path` 사용, `pathlib` 금지
- 표준 라이브러리만. 외부 패키지 금지
- 타입 힌트와 docstring 은 요청 시에만
- 코드 내 주석은 영어. Markdown 문서는 한국어
- 명시적 인자 전달, `**kwargs` 지양
- 대입문의 수직 정렬 금지
- 모든 쓰기는 사전/사후 전체 검증 + 임시파일 후 `os.replace` (SPEC §6)
- 이 도구 자신의 `backlog.json` 도 Phase 3 이후엔 backlog CLI 로만 수정
- 테스트는 fixture 임시 복사본만 수정한다
- 이모지를 사용하지 않는다
- 대상 OS는 Windows, venv 없이 설치
- 파이썬 실행은 반드시 WinPython 절대경로를 쓴다 (맨 `python` 금지):
  `C:\winpython\WPy64-31180\python-3.11.8.amd64\python.exe` (3.11.8)
  - 소스 미설치 실행: `$env:PYTHONPATH="src"` 후 `-m backlog`
  - 설치: `<위 경로> -m pip install -e .`

## 작업 관리

- Phase별 착수 순서는 `docs/PLAN.md`
- 작업 상태는 `backlog.json` (접두어 `BL-`) — Phase 3 이후 `backlog` CLI로만 수정
