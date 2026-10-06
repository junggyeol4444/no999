# AI Novel Factory — Windows 데스크톱 프로그램

이 프로젝트는 웹사이트가 아닙니다. Windows에서 독립 실행되는 **`AI Novel Factory.exe` 데스크톱 프로그램**입니다. 데이터는 사용자의 PC에 있는 SQLite 파일로 저장되며 브라우저나 웹 서버를 사용하지 않습니다.

## 프로그램에서 할 수 있는 일

- TXT, Markdown, DOCX, EPUB, PDF 참고소설 가져오기
- 참고소설 회차 분리 및 문장·문단·대사·전개 속도·클리프행어 분석
- Reference Profile 확인
- 새 장편 프로젝트와 Novel Bible 생성
- 캐릭터의 성격·말투·목표·인물별 지식 저장
- 작품 내부 타임라인과 복선 설치/회수 계획 관리
- 회차 목적, 등장인물, 갈등, 마지막 Hook 설계
- 완성 원고의 분량, 반복 표현, 대사 비율, 참고작 유사성 검사
- 다음 회차 집필에 필요한 Novel Bible, 최근 요약, 캐릭터, 관계, 타임라인과 열린 복선 검색
- OpenAI 호환 API를 이용한 회차 플롯 → 초고 → 품질 검사 → 문제 원고 자동 수정 파이프라인
- 누락 회차·수정 필요 원고·미회수 복선 완결 검사와 EPUB 3 전자책 출력
- 지정 범위 회차 연속 생성, 확정 회차 건너뛰기, 진행 상태 영속화와 안전 중지
- 확정 회차 요약 자동 색인과 현재 플롯에 관련된 과거 기억 유사도 검색

모든 핵심 데이터는 Windows의 `%LOCALAPPDATA%\AI Novel Factory\`에 저장됩니다.

## Windows EXE 만들기

### 가장 간단한 방법

Python 3.11 이상을 설치한 Windows PC에서 다음 파일을 더블 클릭합니다.

```text
build_windows.bat
```

빌드가 완료되면 아래 파일이 생성됩니다.

```text
dist\AI Novel Factory.exe
```

생성된 EXE는 Python 명령이나 웹 서버 없이 더블 클릭해서 실행할 수 있습니다.

빌드된 실행 파일의 핵심 기능을 직접 진단하려면 명령 프롬프트에서 실행합니다.

```bat
"dist\AI Novel Factory.exe" --self-test
```

Windows CI도 EXE 빌드가 끝난 뒤 동일한 진단을 실행합니다. SQLite 생성, 참고작 분석, Novel Bible과 장기 기억 저장, 회차 계획, 품질 검사와 원고 확정 중 하나라도 실패하면 빌드는 실패합니다.

### 명령 프롬프트에서 직접 빌드

```bat
py -3 -m venv .venv-build
.venv-build\Scripts\activate
pip install -e ".[build,documents]"
pyinstaller --noconfirm --clean "AI_Novel_Factory.spec"
```

PyInstaller는 실행 중인 운영체제용 실행 파일을 만들기 때문에 Windows EXE는 Windows 환경에서 빌드해야 합니다. 저장소의 GitHub Actions 워크플로도 `windows-latest`에서 동일한 EXE를 빌드하여 아티팩트로 제공합니다.

## 소스에서 바로 실행

Windows에서는 `run_desktop.bat`을 더블 클릭하거나 다음 명령을 실행합니다.

```bat
py -3 -m novel_factory.desktop
```

Linux/macOS 개발 환경에서는 다음과 같이 실행할 수 있습니다.

```bash
python3 -m novel_factory.desktop
```

## 화면 구성

1. **대시보드** — 작품과 참고소설 현황, 빠른 시작
2. **작품 관리** — Novel Bible 프로젝트 생성 및 선택
3. **참고소설 분석** — 파일 가져오기, 분석 실행, Reference Profile 확인
4. **캐릭터·기억** — 인물 지식, 타임라인, 복선 데이터 등록
5. **회차 제작** — Episode Planner 작성
6. **품질 검사** — 원고 확정 전 반복·유사성·문체 검사
7. **EPUB·출판** — 완결 검사와 확정 회차 EPUB 3 내보내기
8. **연속 자동 제작** — 시작·종료 회차 지정, 순차 생성, 진행률 확인 및 안전 중지

`캐릭터·기억`의 **관련 기억 검색** 탭에서는 인물, 사건, 장소 또는 아이템을 입력해 과거 확정 회차를 검색할 수 있습니다. Writer도 회차 플롯을 만든 다음 같은 색인을 검색하여 최근 5화 밖의 관련 사건을 컨텍스트에 포함합니다. 현재 EXE 내장 색인은 한국어 단어와 글자 단위 특징을 사용한 로컬 유사도 검색이며, 외부 서버로 원고를 전송하지 않습니다.

## AI 회차 자동 제작

`회차 제작` 화면에서 회차 번호를 입력한 뒤 **AI 연결 설정**을 누릅니다. OpenAI 호환 Chat Completions API 주소, 모델과 API 키를 입력하고 **AI로 이 회차 자동 제작**을 실행합니다.

API 키는 프로그램 메모리에만 보관되며 설정 파일이나 SQLite에 저장하지 않습니다. 자동 제작 파이프라인은 다음 순서로 실행됩니다.

```text
Novel Bible 및 관련 기억 검색
→ 참고작 구조 Profile 검색(참고작 원문 제외)
→ 회차 플롯 JSON 생성
→ 회차 본문 생성
→ 분량·반복·대사·참고작 유사성 검사
→ 실패 시 문제 원고 자동 수정 및 재검사
→ 통과 원고와 회차 요약 저장
```

`연속 자동 제작` 화면에서는 예를 들어 1~30화를 지정할 수 있습니다. 각 회차가 품질 검사를 통과한 뒤에만 다음 회차로 진행하며, 이미 `FINAL` 상태인 회차는 다시 생성하지 않습니다. 작업 진행 회차와 상태는 SQLite에 기록되므로 실패·중지 지점을 확인할 수 있습니다.

## CLI 자동화

화면 없이 참고소설 분석 작업을 자동화할 때만 CLI를 사용할 수 있습니다.

```bash
python -m novel_factory.cli analyze reference.txt --title "참고 작품"
python -m novel_factory.cli create-novel "새 작품" --genre 현대판타지 \
  --premise "회귀한 인수 전문가가 부실기업을 재건한다" --episodes 250
python -m novel_factory.cli list
```

## 테스트

```bash
pytest -q
python -m compileall -q novel_factory
```

통합 테스트는 임시 SQLite 데이터베이스에서 참고작 등록 → 구조 분석 → Novel Bible 생성 → 캐릭터·관계·타임라인·복선 등록 → 회차 계획 → 원고 품질 검사 → 장기 기억 검색의 실제 흐름을 검증합니다.

## 현재 MVP 범위

현재 버전은 참고작 분석, 작품 메모리와 로컬 관련 기억 검색, 회차 설계, AI 단일·연속 회차 생성, 품질 검사, 완결 감사와 EPUB 3 출력을 실행합니다. **기획안 전체가 완성된 상태는 아닙니다.** 현재 연속 생성은 프로그램이 실행 중일 때 동작하는 로컬 작업자이며, 임베딩 모델/pgvector 기반 의미 검색, 지정 시각 백그라운드 실행 서비스, 표지 생성 및 플랫폼 출판 Adapter는 아직 구현되지 않았습니다. 현재 구현되지 않은 기능을 완성됐다고 표시하지 않습니다.

Python을 선택한 이유는 단순히 개발이 쉬워서가 아니라 원래 기획안의 기술 스택이 Python이고, 문서 파싱·자연어 분석·AI 모델 SDK 생태계가 가장 성숙하기 때문입니다. SQLite 트랜잭션과 자동 테스트, EXE 내부 자체 진단 및 Windows 빌드 검증을 통해 실행 안정성을 확인합니다. 다만 Windows 전용 네이티브 UI와 설치 프로그램이 최우선이라면 향후 UI 계층만 C#/.NET으로 교체하고 현재 Python 분석 엔진을 별도 프로세스로 유지하는 구성이 적합합니다.
