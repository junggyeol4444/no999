from novel_factory.desktop import NovelFactoryApp
from novel_factory.diagnostics import run_self_test


def test_desktop_helpers_do_not_require_window():
    assert NovelFactoryApp._csv("김도윤, 박서연,  ") == ["김도윤", "박서연"]
    assert NovelFactoryApp._percent(0.4123) == "41.2%"
    assert NovelFactoryApp._percent(None) == "-"


def test_packaged_application_self_test():
    report = run_self_test()
    assert report.passed, report.error
    assert set(report.checks) == {"database", "reference_analysis", "memory", "episode_pipeline", "epub"}
