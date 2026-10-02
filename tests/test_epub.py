from pathlib import Path
from xml.etree import ElementTree
import zipfile

import pytest

from novel_factory.database import Database
from novel_factory.epub import EpubChapter, build_epub
from novel_factory.services import NovelFactory


def test_builds_valid_epub_archive(tmp_path: Path):
    output = build_epub(tmp_path / "book.epub", title="테스트 & 작품", author="작가", language="ko",
                        description="설명", chapters=[EpubChapter(1, "시작 <1>", "첫 문단.\n\n두 번째 문단.")])
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist()[0] == "mimetype"
        assert archive.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert archive.read("mimetype") == b"application/epub+zip"
        ElementTree.fromstring(archive.read("META-INF/container.xml"))
        ElementTree.fromstring(archive.read("OEBPS/package.opf"))
        ElementTree.fromstring(archive.read("OEBPS/nav.xhtml"))
        chapter = archive.read("OEBPS/chapter-0001.xhtml").decode()
        assert "테스트 &amp; 작품" not in chapter
        assert "시작 &lt;1&gt;" in chapter
        assert "두 번째 문단" in chapter


def test_export_and_completion_audit(tmp_path: Path):
    factory = NovelFactory(Database(tmp_path / "factory.db"), tmp_path / "uploads")
    novel = factory.create_novel({"title": "작품", "genre": "판타지", "premise": "완결 검사를 테스트하는 작품입니다.",
                                  "target_episodes": 1, "characters_per_episode": 1000})
    assert factory.completion_audit(novel["id"])["can_complete"] is False
    factory.plan_episode(novel["id"], 1, {"title": "시작", "purpose": "시작"})
    text = "주인공은 문을 열었다. " + "그는 주변을 확인하고 앞으로 조심스럽게 걸어갔다. " * 20
    assert factory.finalize_episode(novel["id"], 1, text)["status"] == "FINAL"
    assert factory.completion_audit(novel["id"])["can_complete"] is True
    output = factory.export_epub(novel["id"], tmp_path / "novel.epub", "작가")
    assert output.exists() and output.stat().st_size > 500


def test_rejects_empty_epub(tmp_path: Path):
    with pytest.raises(ValueError, match="확정 회차"):
        build_epub(tmp_path / "empty.epub", title="빈 책", author="작가", language="ko", description="", chapters=[])

