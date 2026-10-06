from novel_factory.reference import ReferenceAnalyzer, split_episodes


SAMPLE = """제1화 시작
김도윤은 낡은 사무실의 문을 열었다. "이번에는 바꿀 수 있어."
하지만 책상 위에는 검은 수첩이 놓여 있었다. 도대체 누가 둔 것일까?

제2화 거래
그는 첫 투자를 결정했다. "계약하겠습니다."
그 순간 복도에서 낯선 발소리가 들렸다. 새로운 적이 나타난 것이다.
"""


def test_split_and_analyze_reference():
    episodes = split_episodes(SAMPLE)
    assert len(episodes) == 2
    profile = ReferenceAnalyzer().analyze("REF_TEST", "테스트", "txt", SAMPLE)
    assert profile.episode_count == 2
    assert profile.total_characters > 50
    assert 0 < profile.dialogue_ratio < 1
    assert profile.cliffhanger_rate == 1
    assert profile.cliffhanger_types["미스터리"] > 0


def test_plain_text_is_single_episode():
    assert split_episodes("제목 없는 짧은 본문입니다.") == ["제목 없는 짧은 본문입니다."]

