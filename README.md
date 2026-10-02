# AI Novel Factory

장편소설의 참고작 **구조 분석**, Novel Bible과 장기 기억 관리, 회차 설계, 유사성·반복 표현 검사까지 실행하는 백엔드 MVP입니다. 단순 화면 목업이 아니라 SQLite에 데이터를 영속화하고 API와 CLI에서 동일한 제작 엔진을 사용합니다.

## 현재 구현 범위

- TXT·Markdown·DOCX·EPUB 텍스트 추출(PDF는 `documents` 옵션 설치 시 지원)
- 회차 자동 분리와 분량·문장·문단·대사 비율·속도·클리프행어 통계 분석
- Reference Profile 영속화와 작품별/항목별 참고 강도 설정
- Novel Bible, Character Knowledge, Timeline, Foreshadowing, Episode DB
- 회차 플래너 및 Writer용 검색 컨텍스트(최근 요약·인물·타임라인·열린 복선)
- 반복 문장, 분량, 대사 비율, 참고작 구문 유사성을 검사하는 품질 파이프라인
- FastAPI REST API, Swagger 문서, 관리 대시보드, 의존성 없는 관리 CLI

LLM 호출은 특정 공급자에 종속되지 않도록 아직 어댑터 경계 밖에 두었습니다. 현재 MVP는 생성 모델에 전달할 정확한 컨텍스트를 만들고 결과물을 검수·저장하는 기반 계층입니다.

## 빠른 시작

Python 3.11 이상이 필요합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[documents,dev]'
novel-factory serve --port 8000
```

- 관리자 화면: <http://127.0.0.1:8000>
- Swagger API: <http://127.0.0.1:8000/docs>
- 상태 확인: <http://127.0.0.1:8000/api/health>

데이터는 기본적으로 `./data/novel_factory.db`와 `./data/uploads/`에 저장됩니다. `NOVEL_FACTORY_DATA` 환경 변수 또는 CLI의 `--data-dir`로 위치를 바꿀 수 있습니다.

## 의존성 없이 분석 엔진 실행

FastAPI를 설치하지 않아도 Python 표준 라이브러리만으로 TXT·Markdown·DOCX·EPUB 분석과 저장을 실행할 수 있습니다.

```bash
python -m novel_factory.cli --data-dir ./data analyze ./my-novel.txt --title "참고 작품"
python -m novel_factory.cli --data-dir ./data create-novel "새 작품" \
  --genre 현대판타지 --premise "회귀한 인수 전문가가 부실기업을 재건한다" --episodes 250
python -m novel_factory.cli --data-dir ./data list
```

## 핵심 API

| Method | Path | 역할 |
|---|---|---|
| `POST` | `/api/references` | 참고소설 파일 등록 |
| `POST` | `/api/references/{id}/analyze` | Reference Profile 생성 |
| `POST` | `/api/novels` | 작품과 Novel Bible 생성 |
| `POST` | `/api/novels/{id}/references` | 참고작과 항목별 강도 연결 |
| `POST` | `/api/novels/{id}/characters` | 인물·지식·관계 정보 저장 |
| `POST` | `/api/novels/{id}/foreshadowing` | 복선 설치/회수 계획 저장 |
| `POST` | `/api/novels/{id}/timeline` | 작품 내부 시간선 사건 저장 |
| `POST` | `/api/novels/{id}/relationships` | 회차별 인물 관계 변화 저장 |
| `POST` | `/api/novels/{id}/episodes/{no}/plan` | 회차 플롯과 Scene 계획 저장 |
| `PUT` | `/api/novels/{id}/episodes/{no}/finalize` | 원고 품질 검사 및 확정 |
| `GET` | `/api/novels/{id}/episodes/{no}/context` | Writer용 장기 기억 컨텍스트 검색 |

### 작품 생성 예시

```json
{
  "title": "회귀한 CFO는 재벌을 꿈꾼다",
  "genre": "현대판타지",
  "premise": "회귀한 기업 인수 전문가가 과거의 실패를 바로잡는다.",
  "target_episodes": 250,
  "characters_per_episode": 5000,
  "core_material": ["회귀", "기업경영"],
  "atmosphere": "빠르고 지적인 성장물"
}
```

### 참고 강도 연결 예시

```json
{
  "reference_id": "REF_xxxxxxxxxxxx",
  "weights": {
    "pacing": 0.8,
    "cliffhanger": 0.7,
    "character_structure": 0.3,
    "style": 0
  }
}
```

## 테스트

```bash
pytest -q
```

테스트는 참고작 분석과 등록 → 분석 → Novel Bible → 참고작 연결 → 인물·복선 → 회차 계획 → 품질 검사 → 장기 기억 검색의 실제 워크플로를 임시 SQLite DB에서 검증합니다.

## 저작권·유사성 원칙

- 참고작 원문은 Writer 컨텍스트로 전달하지 않습니다.
- 참고작 연결에는 `pacing`, `cliffhanger`, `foreshadowing` 같은 구조 항목만 허용합니다.
- 완성 원고는 연결된 모든 참고작에 대해 구문 유사성 검사를 통과해야 합니다.
- 작품 고유의 Novel Bible이 Reference Profile보다 항상 우선합니다.
