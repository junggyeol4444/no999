from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from .llm import GenerationError, TextGenerator, parse_json_response
from .services import NovelFactory


ProgressCallback = Callable[[str, int], None]


@dataclass
class GenerationResult:
    episode: dict[str, Any]
    attempts: int
    stages: list[str]


class EpisodeOrchestrator:
    """Plan, draft, check and selectively rewrite one episode."""

    def __init__(self, factory: NovelFactory, generator: TextGenerator, max_rewrites: int = 2):
        self.factory = factory
        self.generator = generator
        self.max_rewrites = max_rewrites

    def generate_episode(self, novel_id: str, number: int, progress: ProgressCallback | None = None) -> GenerationResult:
        notify = progress or (lambda _stage, _percent: None)
        stages: list[str] = []
        notify("컨텍스트 검색", 5)
        context = self.factory.memory_context(novel_id, number)
        reference_profiles = self.factory.reference_profiles(novel_id)
        # Raw reference manuscripts are deliberately excluded from every prompt.
        safe_context = {**context, "reference_profiles": reference_profiles}

        notify("회차 플롯 생성", 15)
        plan = self._plan(number, safe_context)
        stages.append("planned")
        try:
            episode = self.factory.plan_episode(novel_id, number, plan)
        except Exception as exc:
            if "UNIQUE constraint" not in str(exc):
                raise
            episode = self.factory.get_episode(novel_id, number)
            plan = episode["outline"]

        notify("초고 집필", 35)
        manuscript = self._draft(number, plan, safe_context)
        stages.append("drafted")
        attempts = 1
        while True:
            notify("품질·유사성 검사", min(85, 55 + attempts * 10))
            episode = self.factory.finalize_episode(novel_id, number, manuscript)
            report = episode["quality"]
            if report["passed"]:
                stages.append("quality_passed")
                break
            if attempts > self.max_rewrites:
                stages.append("revision_required")
                break
            notify("문제 구간 수정", min(90, 65 + attempts * 10))
            manuscript = self._rewrite(manuscript, report, plan, safe_context)
            attempts += 1
            stages.append("rewritten")
        notify("메모리 업데이트 완료", 100)
        return GenerationResult(episode=episode, attempts=attempts, stages=stages)

    def _plan(self, number: int, context: dict[str, Any]) -> dict[str, Any]:
        response = self.generator.generate(
            "당신은 한국 장편 웹소설의 회차 설계자다. Novel Bible은 모든 참고 패턴보다 우선한다. "
            "참고작의 고유명사·문장·장면을 복제하지 말고 통계적 구조만 사용한다. 반드시 JSON만 반환한다.",
            f"{number}화 계획을 작성하라. 필드: title, purpose, required_events, characters, emotion_flow, "
            f"foreshadowing, reward, conflict, hook, scenes. 컨텍스트:\n{self._json(context)}",
            temperature=0.55,
        )
        plan = parse_json_response(response)
        if not str(plan.get("purpose", "")).strip():
            raise GenerationError("AI 회차 계획에 purpose가 없습니다.")
        for field in ("required_events", "characters", "emotion_flow", "foreshadowing", "scenes"):
            if not isinstance(plan.get(field), list):
                plan[field] = []
        return plan

    def _draft(self, number: int, plan: dict[str, Any], context: dict[str, Any]) -> str:
        bible = context["novel_bible"]
        target = bible.get("characters_per_episode", 5000)
        response = self.generator.generate(
            "당신은 오리지널 한국 장편 웹소설 작가다. 제공된 Novel Bible, 인물별 지식 범위, 타임라인을 "
            "절대 위반하지 않는다. 참고작 원문은 없으며 구조 통계만 참고한다. 설명 없이 소설 본문만 반환한다.",
            f"{number}화 본문을 약 {target}자로 작성하라.\n회차 계획:\n{self._json(plan)}\n"
            f"작품 컨텍스트:\n{self._json(context)}",
            temperature=0.8,
        ).strip()
        if not response:
            raise GenerationError("AI가 빈 원고를 반환했습니다.")
        return response

    def _rewrite(self, manuscript: str, report: dict[str, Any], plan: dict[str, Any], context: dict[str, Any]) -> str:
        issues = report.get("issues", [])
        return self.generator.generate(
            "당신은 장편소설 편집자다. 지적된 문제만 수정하고 사건, 인물의 지식, 문체와 분량은 유지한다. "
            "참고작과 유사한 구문은 완전히 다른 표현과 장면 구성으로 바꾼다. 수정 원고만 반환한다.",
            f"문제:\n{self._json(issues)}\n회차 계획:\n{self._json(plan)}\n"
            f"Novel Bible:\n{self._json(context['novel_bible'])}\n원고:\n{manuscript}",
            temperature=0.65,
        ).strip()

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)

