from pathlib import Path

import pytest

from novel_factory.database import Database
from novel_factory.services import NovelFactory


@pytest.fixture
def factory(tmp_path: Path) -> NovelFactory:
    return NovelFactory(Database(tmp_path / "factory.db"), tmp_path / "uploads")


def test_reference_novel_episode_workflow(factory: NovelFactory, tmp_path: Path):
    source = tmp_path / "reference.txt"
    source.write_text("제1화 시작\n그는 문을 열었다. 하지만 안에는 누가 있는 것일까?\n제2화 선택\n그가 말했다. \"계약하지.\"", encoding="utf-8")
    reference = factory.register_reference("참고작", source)
    analyzed = factory.analyze_reference(reference["id"])
    assert analyzed["status"] == "ANALYZED"

    novel = factory.create_novel({"title": "새 작품", "genre": "현대판타지", "premise": "회귀한 경영자가 회사를 되살린다.",
                                  "target_episodes": 10, "characters_per_episode": 5000})
    factory.link_reference(novel["id"], reference["id"], {"pacing": 0.8, "style": 0})
    factory.add_character(novel["id"], {"name": "김도윤", "knowledge": ["회귀 사실"]})
    second = factory.add_character(novel["id"], {"name": "박서연", "knowledge": []})
    first_id = factory.memory_context(novel["id"], 1)["characters"][0]["character_id"]
    factory.add_relationship(novel["id"], {"source_character_id": first_id, "target_character_id": second["character_id"],
                                           "episode": 1, "state": "경계"})
    factory.add_timeline_event(novel["id"], {"episode": 1, "occurred_at": "2026-03-01", "description": "회귀"})
    factory.add_foreshadowing(novel["id"], {"setup_episode": 1, "description": "검은 수첩", "planned_payoff": 8})
    episode = factory.plan_episode(novel["id"], 1, {"purpose": "능력 증명", "characters": ["김도윤"], "hook": "수첩 발견"})
    assert episode["status"] == "PLANNED"

    manuscript = "김도윤은 첫 번째 계약서를 펼쳤다. " + "이번 선택으로 미래를 바꿀 수 있었다. " * 15
    finalized = factory.finalize_episode(novel["id"], 1, manuscript)
    assert finalized["status"] == "FINAL"
    assert finalized["quality"]["passed"] is True
    context = factory.memory_context(novel["id"], 2)
    assert context["novel_bible"]["title"] == "새 작품"
    assert context["characters"][0]["knowledge"] == ["회귀 사실"]
    assert context["open_foreshadowing"][0]["description"] == "검은 수첩"
    assert context["timeline"][0]["description"] == "회귀"
    assert context["relationships"][0]["state"] == "경계"


def test_rejects_unanalyzed_reference(factory: NovelFactory, tmp_path: Path):
    source = tmp_path / "reference.txt"
    source.write_text("본문", encoding="utf-8")
    reference = factory.register_reference("미분석", source)
    novel = factory.create_novel({"title": "작품", "genre": "판타지", "premise": "충분히 긴 작품 전제입니다.", "target_episodes": 3})
    with pytest.raises(ValueError, match="분석이 완료된"):
        factory.link_reference(novel["id"], reference["id"], {"pacing": 1})
