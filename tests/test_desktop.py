from novel_factory.desktop import NovelFactoryApp


def test_desktop_helpers_do_not_require_window():
    assert NovelFactoryApp._csv("김도윤, 박서연,  ") == ["김도윤", "박서연"]
    assert NovelFactoryApp._percent(0.4123) == "41.2%"
    assert NovelFactoryApp._percent(None) == "-"
