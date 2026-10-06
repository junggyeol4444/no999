from pathlib import Path

from novel_factory.database import Database
from novel_factory.memory import LocalMemoryIndex
from novel_factory.services import NovelFactory


def test_local_memory_search_ranks_relevant_episode(tmp_path: Path):
    database = Database(tmp_path / "memory.db")
    factory = NovelFactory(database, tmp_path / "uploads")
    novel = factory.create_novel({"title": "검색 작품", "genre": "현대판타지", "premise": "기업 계약 이야기입니다.",
                                  "target_episodes": 10})
    index = LocalMemoryIndex(database)
    index.index(novel["id"], 3, "EPISODE_SUMMARY", "주인공은 세광전자 반도체 공장 인수 계약을 체결했다.")
    index.index(novel["id"], 5, "EPISODE_SUMMARY", "주인공은 산에서 마법 검술을 수련했다.")
    index.index(novel["id"], 7, "EPISODE_SUMMARY", "경쟁 기업이 반도체 공급 계약을 방해했다.")
    hits = index.search(novel["id"], "반도체 기업 계약", before_episode=10, limit=2)
    assert [hit.episode for hit in hits] == [7, 3]
    assert hits[0].score >= hits[1].score > 0


def test_final_episode_is_indexed_and_future_is_excluded(tmp_path: Path):
    factory = NovelFactory(Database(tmp_path / "factory.db"), tmp_path / "uploads")
    novel = factory.create_novel({"title": "기억 작품", "genre": "현대판타지", "premise": "기업 인수를 다루는 장편 작품입니다.",
                                  "target_episodes": 5, "characters_per_episode": 1000})
    factory.plan_episode(novel["id"], 1, {"purpose": "첫 기업 인수"})
    manuscript = "김도윤은 세광전자 인수 계약서를 검토했다. " + "반도체 공장의 가치를 확인하고 계약 조건을 조정했다. " * 15
    factory.finalize_episode(novel["id"], 1, manuscript)
    hits = factory.search_memories(novel["id"], "세광전자 인수", before_episode=2)
    assert hits[0]["episode"] == 1
    assert "세광전자" in hits[0]["content"]
    assert factory.search_memories(novel["id"], "세광전자", before_episode=1) == []
