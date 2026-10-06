from pathlib import Path

import pytest

from novel_factory.batch import BatchGenerator
from novel_factory.database import Database
from novel_factory.orchestrator import EpisodeOrchestrator
from novel_factory.services import NovelFactory


class BatchFakeGenerator:
    def generate(self, system: str, user: str, *, temperature: float = 0.7) -> str:
        if "JSON만 반환" in system:
            return '{"title":"자동 회차","purpose":"전진","characters":[],"required_events":[],"emotion_flow":[],"foreshadowing":[],"scenes":[],"hook":"다음 위기"}'
        return "주인공은 다음 단계로 나아갔다. " + "그는 상황을 확인하고 신중하게 새로운 결정을 내렸다. " * 18


def make_batch(tmp_path: Path, target: int = 3):
    factory = NovelFactory(Database(tmp_path / "factory.db"), tmp_path / "uploads")
    novel = factory.create_novel({"title": "연속 작품", "genre": "판타지", "premise": "연속 생성을 검증하는 작품입니다.",
                                  "target_episodes": target, "characters_per_episode": 1000})
    worker = BatchGenerator(factory, EpisodeOrchestrator(factory, BatchFakeGenerator()))
    return factory, novel, worker


def test_generates_episode_range_and_persists_progress(tmp_path: Path):
    factory, novel, worker = make_batch(tmp_path)
    job = worker.create_job(novel["id"], 1, 3)
    events = []
    result = worker.run(job["id"], events.append)
    assert result.job["status"] == "COMPLETED"
    assert result.generated == [1, 2, 3]
    assert result.job["completed_count"] == 3
    assert [episode["status"] for episode in factory.list_episodes(novel["id"])] == ["FINAL"] * 3
    assert events[-1]["percent"] == 100


def test_skips_existing_final_episode(tmp_path: Path):
    factory, novel, worker = make_batch(tmp_path, 2)
    factory.plan_episode(novel["id"], 1, {"purpose": "기존 회차"})
    text = "기존 원고다. " + "주인공은 충분한 정보를 검토하고 올바른 판단을 내렸다. " * 20
    factory.finalize_episode(novel["id"], 1, text)
    result = worker.run(worker.create_job(novel["id"], 1, 2)["id"])
    assert result.skipped == [1]
    assert result.generated == [2]


def test_rejects_invalid_or_concurrent_jobs(tmp_path: Path):
    _factory, novel, worker = make_batch(tmp_path)
    with pytest.raises(ValueError, match="범위"):
        worker.create_job(novel["id"], 3, 2)
    worker.create_job(novel["id"], 1, 2)
    with pytest.raises(ValueError, match="이미"):
        worker.create_job(novel["id"], 2, 3)

