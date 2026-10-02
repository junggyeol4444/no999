from __future__ import annotations

import html
import re
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class EpubChapter:
    number: int
    title: str
    text: str


def _paragraphs(text: str) -> str:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    return "\n".join(f"<p>{html.escape(block).replace(chr(10), '<br/>')}</p>" for block in blocks)


def build_epub(
    destination: str | Path,
    *,
    title: str,
    author: str,
    language: str,
    description: str,
    chapters: Iterable[EpubChapter],
) -> Path:
    """Create a standards-oriented EPUB 3 archive using only stdlib."""
    chapter_list = sorted(chapters, key=lambda chapter: chapter.number)
    if not chapter_list:
        raise ValueError("EPUB으로 내보낼 확정 회차가 없습니다.")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    book_id = f"urn:uuid:{uuid.uuid4()}"
    modified = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = []
    spine = []
    navigation = []
    with zipfile.ZipFile(destination, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/package.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>""")
        for index, chapter in enumerate(chapter_list, start=1):
            file_name = f"chapter-{index:04d}.xhtml"
            chapter_id = f"chapter-{index}"
            safe_title = html.escape(chapter.title or f"{chapter.number}화")
            document = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{html.escape(language)}">
<head><meta charset="utf-8"/><title>{safe_title}</title><link rel="stylesheet" href="style.css" type="text/css"/></head>
<body><section epub:type="chapter" xmlns:epub="http://www.idpf.org/2007/ops"><h1>{safe_title}</h1>{_paragraphs(chapter.text)}</section></body>
</html>"""
            archive.writestr(f"OEBPS/{file_name}", document)
            manifest.append(f'<item id="{chapter_id}" href="{file_name}" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="{chapter_id}"/>')
            navigation.append(f'<li><a href="{file_name}">{safe_title}</a></li>')
        archive.writestr("OEBPS/style.css", "body{font-family:serif;line-height:1.8;margin:5%;}h1{text-align:center;margin:2em 0;}p{text-indent:1em;margin:.7em 0;}")
        nav = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{html.escape(language)}">
<head><title>목차</title></head><body><nav epub:type="toc" id="toc"><h1>목차</h1><ol>{''.join(navigation)}</ol></nav></body></html>"""
        archive.writestr("OEBPS/nav.xhtml", nav)
        package = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id" xml:lang="{html.escape(language)}">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="book-id">{book_id}</dc:identifier><dc:title>{html.escape(title)}</dc:title>
<dc:creator>{html.escape(author)}</dc:creator><dc:language>{html.escape(language)}</dc:language>
<dc:description>{html.escape(description)}</dc:description><meta property="dcterms:modified">{modified}</meta>
</metadata><manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
<item id="style" href="style.css" media-type="text/css"/>{''.join(manifest)}</manifest>
<spine>{''.join(spine)}</spine></package>"""
        archive.writestr("OEBPS/package.opf", package)
    return destination
