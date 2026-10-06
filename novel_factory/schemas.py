from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ReferenceProfile:
    reference_id: str
    title: str
    source_format: str
    total_characters: int
    episode_count: int
    avg_episode_length: float
    avg_sentence_length: float
    avg_paragraph_length: float
    dialogue_ratio: float
    description_ratio: float
    short_sentence_ratio: float
    cliffhanger_rate: float
    cliffhanger_types: dict[str, float]
    plot_speed: str
    structural_features: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QualityIssue:
    checker: str
    severity: str
    message: str
    scene: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QualityReport:
    passed: bool
    score: float
    issues: list[QualityIssue]
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "issues": [issue.to_dict() for issue in self.issues],
            "metrics": self.metrics,
        }

