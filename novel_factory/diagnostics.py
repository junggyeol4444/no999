from __future__ import annotations

import json
import sqlite3
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .database import Database
from .services import NovelFactory


@dataclass
class DiagnosticReport:
    passed: bool
    checks: dict[str, str]
    error: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def run_self_test() -> DiagnosticReport:
    """Run the critical production workflow against an isolated database.

    This is intentionally available inside the packaged EXE. The Windows CI
    executes it after building, so a bundle that cannot import modules, create
    its database, analyze a document, or finalize an episode is rejected.
    """
    checks: dict[str, str] = {}
    try:
        with tempfile.TemporaryDirectory(prefix="novel-factory-check-") as directory:
            root = Path(directory)
            factory = NovelFactory(Database(root / "factory.db"), root / "uploads")
            checks["database"] = f"SQLite {sqlite3.sqlite_version} initialized"

            source = root / "reference.txt"
            source.write_text(
                "제1화 시작\n그는 계약서를 펼쳤다. 하지만 이 거래에는 어떤 비밀이 있을까?\n\n"
                "제2화 선택\n그가 말했다. \"계약하겠습니다.\" 낯선 경쟁자가 나타났다.",
                encoding="utf-8",
            )
            reference = factory.register_reference("진단 참고작", source)
            reference = factory.analyze_reference(reference["id"])
            assert reference["status"] == "ANALYZED"
            assert reference["profile"]["episode_count"] == 2
            checks["reference_analysis"] = "2 episodes analyzed"

            novel = factory.create_novel({
                "title": "진단 작품", "genre": "현대판타지",
                "premise": "실행 파일 진단을 위한 장편소설 프로젝트입니다.",
                "target_episodes": 10, "characters_per_episode": 5000,
            })
            factory.link_reference(novel["id"], reference["id"], {"pacing": 0.8, "style": 0.0})
            character = factory.add_character(novel["id"], {"name": "김도윤", "knowledge": ["회귀 사실"]})
            assert character["character_id"]
            factory.add_timeline_event(novel["id"], {"episode": 1, "occurred_at": "1일차", "description": "회귀"})
            factory.add_foreshadowing(novel["id"], {"setup_episode": 1, "description": "검은 수첩", "planned_payoff": 8})
            checks["memory"] = "bible, character, timeline and foreshadowing stored"

            factory.plan_episode(novel["id"], 1, {
                "purpose": "주인공 능력 증명", "characters": ["김도윤"], "hook": "수첩 발견",
            })
            manuscript = "김도윤은 계약서를 펼쳤다. " + "이번 선택으로 실패한 미래를 바꿀 수 있었다. " * 15
            episode = factory.finalize_episode(novel["id"], 1, manuscript)
            assert episode["quality"]["passed"] is True
            assert factory.memory_context(novel["id"], 2)["open_foreshadowing"]
            checks["episode_pipeline"] = "plan, quality check, finalization and retrieval passed"
        return DiagnosticReport(True, checks)
    except Exception as exc:
        return DiagnosticReport(False, checks, f"{type(exc).__name__}: {exc}")

