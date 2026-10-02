from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher

from .schemas import QualityIssue, QualityReport


class QualityPipeline:
    """Deterministic first-pass checks run before an LLM editor is invoked."""

    def check(
        self,
        manuscript: str,
        reference_texts: list[str] | None = None,
        known_names: list[str] | None = None,
    ) -> QualityReport:
        issues: list[QualityIssue] = []
        normalized = manuscript.strip()
        if len(normalized) < 300:
            issues.append(QualityIssue("length", "ERROR", "회차 본문이 300자보다 짧습니다."))

        sentences = [part.strip() for part in re.split(r"(?<=[.!?。！？])\s+|\n+", normalized) if part.strip()]
        repeated = [sentence for sentence, count in Counter(sentences).items() if count >= 3 and len(sentence) >= 8]
        for sentence in repeated[:5]:
            issues.append(QualityIssue("repetition", "WARNING", f"동일 문장이 3회 이상 반복됩니다: {sentence[:40]}"))

        phrase_pattern = re.compile(r"[가-힣A-Za-z0-9 ]{12,80}")
        manuscript_phrases = phrase_pattern.findall(normalized)
        max_similarity = 0.0
        for reference in reference_texts or []:
            reference_phrases = phrase_pattern.findall(reference)
            candidates = reference_phrases[:2000]
            for phrase in manuscript_phrases[:500]:
                for candidate in candidates:
                    if abs(len(phrase) - len(candidate)) > 10:
                        continue
                    max_similarity = max(max_similarity, SequenceMatcher(None, phrase, candidate).ratio())
                    if max_similarity >= 0.92:
                        break
                if max_similarity >= 0.92:
                    break
        if max_similarity >= 0.82:
            severity = "ERROR" if max_similarity >= 0.92 else "WARNING"
            issues.append(QualityIssue("similarity", severity, f"참고작과 높은 구문 유사도({max_similarity:.0%})가 감지되었습니다."))

        dialogue_length = sum(len(item) for item in re.findall(r'["“][^"”\n]+["”]', normalized))
        dialogue_ratio = dialogue_length / max(1, len(normalized))
        if dialogue_ratio > 0.75:
            issues.append(QualityIssue("style", "WARNING", "대사 비율이 75%를 초과합니다."))
        if known_names and not any(name in normalized for name in known_names):
            issues.append(QualityIssue("continuity", "WARNING", "등록된 주요 인물이 본문에 등장하지 않습니다."))

        penalty = sum(20 if issue.severity == "ERROR" else 5 for issue in issues)
        score = max(0.0, 100.0 - penalty)
        return QualityReport(
            passed=not any(issue.severity == "ERROR" for issue in issues),
            score=score,
            issues=issues,
            metrics={"dialogue_ratio": round(dialogue_ratio, 4), "max_reference_similarity": round(max_similarity, 4)},
        )

