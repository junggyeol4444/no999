from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from .database import Database
from .quality import QualityPipeline
from .reference import ReferenceAnalyzer, extract_text


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class NovelFactory:
    def __init__(self, database: Database, upload_dir: str | Path):
        self.db = database
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.analyzer = ReferenceAnalyzer()
        self.quality = QualityPipeline()

    def register_reference(self, title: str, source: str | Path) -> dict[str, Any]:
        source_path = Path(source)
        reference_id = new_id("REF")
        destination = self.upload_dir / f"{reference_id}{source_path.suffix.lower()}"
        shutil.copyfile(source_path, destination)
        self.db.execute(
            "INSERT INTO reference_works(id,title,filename,source_format,status,raw_path) VALUES(?,?,?,?,?,?)",
            (reference_id, title, source_path.name, source_path.suffix.lower().lstrip("."), "UPLOADED", str(destination)),
        )
        return self.get_reference(reference_id)

    def analyze_reference(self, reference_id: str) -> dict[str, Any]:
        record = self._required("reference_works", reference_id)
        self.db.execute("UPDATE reference_works SET status='ANALYZING' WHERE id=?", (reference_id,))
        try:
            text = extract_text(record["raw_path"])
            profile = self.analyzer.analyze(reference_id, record["title"], record["source_format"], text)
        except Exception:
            self.db.execute("UPDATE reference_works SET status='FAILED' WHERE id=?", (reference_id,))
            raise
        self.db.execute(
            "UPDATE reference_works SET status='ANALYZED', profile_json=? WHERE id=?",
            (self.db.json(profile.to_dict()), reference_id),
        )
        return self.get_reference(reference_id)

    def get_reference(self, reference_id: str) -> dict[str, Any]:
        result = self._required("reference_works", reference_id)
        result["profile"] = json.loads(result.pop("profile_json")) if result.get("profile_json") else None
        return result

    def list_references(self) -> list[dict[str, Any]]:
        return [self.get_reference(row["id"]) for row in self.db.fetch_all("SELECT id FROM reference_works ORDER BY created_at DESC")]

    def create_novel(self, data: dict[str, Any]) -> dict[str, Any]:
        novel_id = new_id("NOVEL")
        bible = {
            "title": data["title"], "genre": data["genre"], "logline": data["premise"],
            "core_material": data.get("core_material", []), "atmosphere": data.get("atmosphere", ""),
            "point_of_view": data.get("point_of_view", "3인칭 제한"),
            "target_audience": data.get("target_audience", "웹소설 독자"),
            "target_episodes": data["target_episodes"],
            "characters_per_episode": data.get("characters_per_episode", 5000), "ending": data.get("ending", ""),
        }
        self.db.execute(
            "INSERT INTO novels(id,title,genre,premise,target_episodes,characters_per_episode,atmosphere,bible_json) VALUES(?,?,?,?,?,?,?,?)",
            (novel_id, data["title"], data["genre"], data["premise"], data["target_episodes"],
             data.get("characters_per_episode", 5000), data.get("atmosphere", ""), self.db.json(bible)),
        )
        return self.get_novel(novel_id)

    def get_novel(self, novel_id: str) -> dict[str, Any]:
        novel = self._required("novels", novel_id)
        novel["bible"] = json.loads(novel.pop("bible_json"))
        novel["references"] = self.db.fetch_all(
            "SELECT reference_id, weights_json FROM novel_references WHERE novel_id=?", (novel_id,)
        )
        for item in novel["references"]:
            item["weights"] = json.loads(item.pop("weights_json"))
        return novel

    def list_novels(self) -> list[dict[str, Any]]:
        return [self.get_novel(row["id"]) for row in self.db.fetch_all("SELECT id FROM novels ORDER BY created_at DESC")]

    def reference_profiles(self, novel_id: str) -> list[dict[str, Any]]:
        """Return only structural profiles and weights, never reference prose."""
        rows = self.db.fetch_all(
            "SELECT r.id,r.title,r.profile_json,nr.weights_json FROM reference_works r "
            "JOIN novel_references nr ON nr.reference_id=r.id WHERE nr.novel_id=? AND r.status='ANALYZED'",
            (novel_id,),
        )
        return [{"reference_id": row["id"], "title": row["title"], "profile": json.loads(row["profile_json"]),
                 "weights": json.loads(row["weights_json"])} for row in rows]

    def link_reference(self, novel_id: str, reference_id: str, weights: dict[str, float]) -> None:
        self._required("novels", novel_id)
        reference = self._required("reference_works", reference_id)
        if reference["status"] != "ANALYZED":
            raise ValueError("분석이 완료된 참고소설만 연결할 수 있습니다.")
        allowed = {"pacing", "episode_structure", "cliffhanger", "foreshadowing", "character_structure", "emotion", "dialogue", "style"}
        if not weights or set(weights) - allowed or any(not 0 <= value <= 1 for value in weights.values()):
            raise ValueError("참고 강도는 허용된 항목별 0~1 값이어야 합니다.")
        self.db.execute(
            "INSERT OR REPLACE INTO novel_references(novel_id,reference_id,weights_json) VALUES(?,?,?)",
            (novel_id, reference_id, self.db.json(weights)),
        )

    def add_character(self, novel_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self._required("novels", novel_id)
        character_id = new_id("CHAR")
        data = {"character_id": character_id, **data}
        self.db.execute("INSERT INTO characters(id,novel_id,data_json) VALUES(?,?,?)", (character_id, novel_id, self.db.json(data)))
        return data

    def add_foreshadowing(self, novel_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self._required("novels", novel_id)
        item_id = new_id("FS")
        self.db.execute(
            "INSERT INTO foreshadowing(id,novel_id,setup_episode,description,planned_payoff,status) VALUES(?,?,?,?,?,?)",
            (item_id, novel_id, data["setup_episode"], data["description"], data.get("planned_payoff"), "OPEN"),
        )
        return self.db.fetch_one("SELECT * FROM foreshadowing WHERE id=?", (item_id,)) or {}

    def add_timeline_event(self, novel_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self._required("novels", novel_id)
        event_id = new_id("TIME")
        self.db.execute(
            "INSERT INTO timeline(id,novel_id,episode,occurred_at,description) VALUES(?,?,?,?,?)",
            (event_id, novel_id, data["episode"], data["occurred_at"], data["description"]),
        )
        return self.db.fetch_one("SELECT * FROM timeline WHERE id=?", (event_id,)) or {}

    def add_relationship(self, novel_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self._required("novels", novel_id)
        relationship_id = new_id("REL")
        self.db.execute(
            "INSERT INTO relationships(id,novel_id,source_character_id,target_character_id,episode,state,description) VALUES(?,?,?,?,?,?,?)",
            (relationship_id, novel_id, data["source_character_id"], data["target_character_id"],
             data["episode"], data["state"], data.get("description", "")),
        )
        return self.db.fetch_one("SELECT * FROM relationships WHERE id=?", (relationship_id,)) or {}

    def plan_episode(self, novel_id: str, number: int, data: dict[str, Any]) -> dict[str, Any]:
        novel = self.get_novel(novel_id)
        if not 1 <= number <= novel["target_episodes"]:
            raise ValueError("회차 번호가 작품의 목표 범위를 벗어났습니다.")
        episode_id = new_id("EP")
        title = data.get("title") or f"{number}화"
        outline = {
            "purpose": data["purpose"], "required_events": data.get("required_events", []),
            "characters": data.get("characters", []), "emotion_flow": data.get("emotion_flow", []),
            "foreshadowing": data.get("foreshadowing", []), "reward": data.get("reward", ""),
            "conflict": data.get("conflict", ""), "hook": data.get("hook", ""), "scenes": data.get("scenes", []),
        }
        self.db.execute(
            "INSERT INTO episodes(id,novel_id,number,title,outline_json) VALUES(?,?,?,?,?)",
            (episode_id, novel_id, number, title, self.db.json(outline)),
        )
        return self.get_episode(novel_id, number)

    def finalize_episode(self, novel_id: str, number: int, manuscript: str) -> dict[str, Any]:
        episode = self.get_episode(novel_id, number)
        references = self.db.fetch_all(
            "SELECT r.raw_path FROM reference_works r JOIN novel_references nr ON nr.reference_id=r.id WHERE nr.novel_id=?",
            (novel_id,),
        )
        reference_texts = [extract_text(item["raw_path"]) for item in references]
        characters = self.db.fetch_all("SELECT data_json FROM characters WHERE novel_id=?", (novel_id,))
        names = [json.loads(item["data_json"]).get("name", "") for item in characters]
        report = self.quality.check(manuscript, reference_texts, [name for name in names if name])
        status = "FINAL" if report.passed else "REVISION_REQUIRED"
        summary = self._summarize(manuscript)
        self.db.execute(
            "UPDATE episodes SET draft=?,final_text=?,summary_json=?,quality_json=?,status=? WHERE id=?",
            (manuscript, manuscript if report.passed else "", self.db.json(summary), self.db.json(report.to_dict()), status, episode["id"]),
        )
        return self.get_episode(novel_id, number)

    def get_episode(self, novel_id: str, number: int) -> dict[str, Any]:
        episode = self.db.fetch_one("SELECT * FROM episodes WHERE novel_id=? AND number=?", (novel_id, number))
        if not episode:
            raise KeyError(f"회차를 찾을 수 없습니다: {number}")
        for source, target in (("outline_json", "outline"), ("summary_json", "summary"), ("quality_json", "quality")):
            raw = episode.pop(source)
            episode[target] = json.loads(raw) if raw else None
        return episode

    def memory_context(self, novel_id: str, episode_number: int) -> dict[str, Any]:
        novel = self.get_novel(novel_id)
        characters = [json.loads(row["data_json"]) for row in self.db.fetch_all("SELECT data_json FROM characters WHERE novel_id=?", (novel_id,))]
        timeline = self.db.fetch_all("SELECT * FROM timeline WHERE novel_id=? AND episode<=? ORDER BY episode", (novel_id, episode_number))
        relationships = self.db.fetch_all(
            "SELECT * FROM relationships WHERE novel_id=? AND episode<=? ORDER BY episode", (novel_id, episode_number)
        )
        foreshadowing = self.db.fetch_all(
            "SELECT * FROM foreshadowing WHERE novel_id=? AND status IN ('OPEN','DEVELOPING') AND setup_episode<=?", (novel_id, episode_number)
        )
        recent = self.db.fetch_all(
            "SELECT number,title,summary_json FROM episodes WHERE novel_id=? AND number<? ORDER BY number DESC LIMIT 5", (novel_id, episode_number)
        )
        return {"novel_bible": novel["bible"], "characters": characters, "timeline": timeline, "relationships": relationships,
                "open_foreshadowing": foreshadowing, "recent_summaries": [json.loads(row["summary_json"]) for row in recent]}

    def _required(self, table: str, record_id: str) -> dict[str, Any]:
        if table not in {"reference_works", "novels"}:
            raise ValueError("허용되지 않은 테이블입니다.")
        record = self.db.fetch_one(f"SELECT * FROM {table} WHERE id=?", (record_id,))
        if not record:
            raise KeyError(f"{record_id}을(를) 찾을 수 없습니다.")
        return record

    @staticmethod
    def _summarize(text: str) -> dict[str, Any]:
        sentences = [part.strip() for part in text.replace("\n", " ").split(".") if part.strip()]
        return {"summary": ". ".join(sentences[:3])[:500], "character_count": len(text), "new_facts": []}
