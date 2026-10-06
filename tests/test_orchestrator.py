from pathlib import Path

from novel_factory.database import Database
from novel_factory.orchestrator import EpisodeOrchestrator
from novel_factory.services import NovelFactory


class FakeGenerator:
    def __init__(self):
        self.calls = 0

    def generate(self, system: str, user: str, *, temperature: float = 0.7) -> str:
        self.calls += 1
        if self.calls == 1:
            return """```json
            {"title":"첫 거래","purpose":"주인공의 능력 증명","required_events":["계약"],
             "characters":["김도윤"],"emotion_flow":["불안","확신"],"foreshadowing":[],
             "reward":"첫 수익","conflict":"정보 부족","hook":"의문의 전화","scenes":[]}
            ```"""
        return "김도윤은 계약서를 확인했다. " + "그는 충분한 근거를 확인한 뒤 신중하게 결정을 내렸다. " * 20


def test_orchestrator_plans_writes_checks_and_finalizes(tmp_path: Path):
    factory = NovelFactory(Database(tmp_path / "factory.db"), tmp_path / "uploads")
    novel = factory.create_novel({
        "title": "새 작품", "genre": "현대판타지", "premise": "회귀한 전문가가 회사를 재건한다.",
        "target_episodes": 10, "characters_per_episode": 5000,
    })
    factory.add_character(novel["id"], {"name": "김도윤", "knowledge": ["회귀 사실"]})
    progress = []
    result = EpisodeOrchestrator(factory, FakeGenerator()).generate_episode(
        novel["id"], 1, lambda stage, percent: progress.append((stage, percent))
    )
    assert result.episode["status"] == "FINAL"
    assert result.episode["outline"]["hook"] == "의문의 전화"
    assert result.stages == ["planned", "drafted", "quality_passed"]
    assert progress[-1] == ("메모리 업데이트 완료", 100)


def test_reference_profiles_never_include_raw_text(tmp_path: Path):
    factory = NovelFactory(Database(tmp_path / "factory.db"), tmp_path / "uploads")
    source = tmp_path / "reference.txt"
    source.write_text("제1화\n비밀 원문 문장입니다. 왜 그런 것일까?", encoding="utf-8")
    reference = factory.register_reference("참고작", source)
    factory.analyze_reference(reference["id"])
    novel = factory.create_novel({"title": "작품", "genre": "판타지", "premise": "충분히 긴 작품 전제입니다.", "target_episodes": 3})
    factory.link_reference(novel["id"], reference["id"], {"pacing": 1.0})
    profiles = factory.reference_profiles(novel["id"])
    assert "raw_path" not in profiles[0]
    assert "비밀 원문 문장" not in str(profiles)

