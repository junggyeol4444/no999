from __future__ import annotations

import html
import io
import re
import statistics
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from .schemas import ReferenceProfile


SUPPORTED_FORMATS = {".txt", ".md", ".markdown", ".docx", ".epub", ".pdf"}
CHAPTER_PATTERN = re.compile(
    r"(?im)^(?:\s*(?:제\s*)?\d{1,4}\s*(?:화|장|회)|\s*chapter\s+\d+|\s*프롤로그|\s*에필로그).*$"
)
SENTENCE_PATTERN = re.compile(r"[^.!?。！？\n]+[.!?。！？]?", re.MULTILINE)
QUOTE_PATTERN = re.compile(r"(?:\"[^\"\n]+\"|'[^'\n]+'|“[^”\n]+”|‘[^’\n]+’)" )
TAG_PATTERN = re.compile(r"<[^>]+>")


def extract_text(path: str | Path) -> str:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise ValueError(f"지원하지 않는 형식입니다: {suffix}")
    if suffix in {".txt", ".md", ".markdown"}:
        return _decode_text(source.read_bytes())
    if suffix == ".docx":
        return _extract_docx(source)
    if suffix == ".epub":
        return _extract_epub(source)
    return _extract_pdf(source)


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("텍스트 인코딩을 확인할 수 없습니다.")


def _extract_docx(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ValueError("올바른 DOCX 파일이 아닙니다.") from exc
    root = ElementTree.fromstring(xml)
    paragraphs = []
    for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
        text = "".join(node.text or "" for node in paragraph.iter() if node.tag.endswith("}t"))
        if text.strip():
            paragraphs.append(text.strip())
    return "\n\n".join(paragraphs)


def _extract_epub(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            names = sorted(name for name in archive.namelist() if name.lower().endswith((".xhtml", ".html", ".htm")))
            documents = [_html_to_text(_decode_text(archive.read(name))) for name in names]
    except zipfile.BadZipFile as exc:
        raise ValueError("올바른 EPUB 파일이 아닙니다.") from exc
    if not documents:
        raise ValueError("EPUB에서 본문을 찾지 못했습니다.")
    return "\n\n".join(filter(None, documents))


def _html_to_text(document: str) -> str:
    document = re.sub(r"(?i)<(?:br|/p|/div|/h[1-6])[^>]*>", "\n", document)
    return html.unescape(TAG_PATTERN.sub("", document)).strip()


def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF 분석에는 documents 옵션이 필요합니다: pip install '.[documents]'") from exc
    reader = PdfReader(io.BytesIO(path.read_bytes()))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def split_episodes(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    matches = list(CHAPTER_PATTERN.finditer(text))
    if not matches:
        return [text] if text else []
    episodes: list[str] = []
    if text[: matches[0].start()].strip():
        episodes.append(text[: matches[0].start()].strip())
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        episodes.append(text[match.start():end].strip())
    return [episode for episode in episodes if episode]


class ReferenceAnalyzer:
    cliffhanger_patterns = {
        "정보 공개": re.compile(r"(사실은|정체|알고 보니|비밀|밝혀)"),
        "위기 발생": re.compile(r"(위험|비명|폭발|피가|죽|습격|쫓아)"),
        "새로운 적 등장": re.compile(r"(적|라이벌|낯선|그자가|등장)"),
        "반전": re.compile(r"(하지만|그러나|아니었다|뜻밖|반전)"),
        "미스터리": re.compile(r"(왜|누구|무엇|어째서|\?)"),
        "약속": re.compile(r"(반드시|약속|기다려|돌아오)"),
    }

    def analyze(self, reference_id: str, title: str, source_format: str, text: str) -> ReferenceProfile:
        episodes = split_episodes(text)
        if not episodes or not text.strip():
            raise ValueError("분석할 본문이 없습니다.")
        sentences = [item.strip() for item in SENTENCE_PATTERN.findall(text) if item.strip()]
        paragraphs = [item.strip() for item in re.split(r"\n\s*\n|\n", text) if item.strip()]
        sentence_lengths = [len(re.sub(r"\s", "", item)) for item in sentences]
        paragraph_lengths = [len(re.sub(r"\s", "", item)) for item in paragraphs]
        dialogue_characters = sum(len(match.group(0)) for match in QUOTE_PATTERN.finditer(text))
        visible_characters = max(1, len(re.sub(r"\s", "", text)))
        cliffhanger_counts = {name: 0 for name in self.cliffhanger_patterns}
        cliffhanger_episodes = 0
        for episode in episodes:
            tail = episode[-max(150, len(episode) // 10):]
            found = False
            for name, pattern in self.cliffhanger_patterns.items():
                if pattern.search(tail):
                    cliffhanger_counts[name] += 1
                    found = True
            cliffhanger_episodes += int(found)
        total_cliffhangers = sum(cliffhanger_counts.values()) or 1
        average_episode = visible_characters / len(episodes)
        return ReferenceProfile(
            reference_id=reference_id,
            title=title,
            source_format=source_format,
            total_characters=visible_characters,
            episode_count=len(episodes),
            avg_episode_length=round(average_episode, 1),
            avg_sentence_length=round(statistics.fmean(sentence_lengths), 1) if sentence_lengths else 0,
            avg_paragraph_length=round(statistics.fmean(paragraph_lengths), 1) if paragraph_lengths else 0,
            dialogue_ratio=round(dialogue_characters / max(1, len(text)), 4),
            description_ratio=round(1 - dialogue_characters / max(1, len(text)), 4),
            short_sentence_ratio=round(sum(length <= 20 for length in sentence_lengths) / max(1, len(sentence_lengths)), 4),
            cliffhanger_rate=round(cliffhanger_episodes / len(episodes), 4),
            cliffhanger_types={name: round(count / total_cliffhangers, 4) for name, count in cliffhanger_counts.items()},
            plot_speed="fast" if average_episode < 4500 else "normal" if average_episode < 6500 else "slow",
            structural_features={
                "episode_length_stddev": round(statistics.pstdev([len(ep) for ep in episodes]), 1),
                "question_ending_rate": round(sum(ep.rstrip().endswith("?") for ep in episodes) / len(episodes), 4),
            },
        )

