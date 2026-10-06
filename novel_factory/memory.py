from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .database import Database


TOKEN_PATTERN = re.compile(r"[가-힣]{2,}|[A-Za-z0-9_]{2,}")


@dataclass(frozen=True)
class MemoryHit:
    episode: int
    source_type: str
    content: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {"episode": self.episode, "source_type": self.source_type, "content": self.content, "score": self.score}


class LocalMemoryIndex:
    """Deterministic local similarity index suitable for the offline EXE.

    It combines Korean/Latin word tokens with Korean character bigrams and a
    stable hashing vector. The interface can later be replaced by pgvector or
    an embedding provider without changing the orchestration layer.
    """

    def __init__(self, database: Database, dimensions: int = 512):
        self.db = database
        self.dimensions = dimensions

    def index(self, novel_id: str, episode: int, source_type: str, content: str) -> None:
        content = content.strip()
        if not content:
            return
        vector = self.embed(content)
        existing = self.db.fetch_one(
            "SELECT id FROM memory_documents WHERE novel_id=? AND episode=? AND source_type=?",
            (novel_id, episode, source_type),
        )
        if existing:
            self.db.execute(
                "UPDATE memory_documents SET content=?,vector_json=? WHERE id=?",
                (content, self.db.json(vector), existing["id"]),
            )
        else:
            self.db.execute(
                "INSERT INTO memory_documents(id,novel_id,episode,source_type,content,vector_json) VALUES(?,?,?,?,?,?)",
                (f"MEM_{uuid.uuid4().hex[:12]}", novel_id, episode, source_type, content, self.db.json(vector)),
            )

    def search(self, novel_id: str, query: str, *, before_episode: int | None = None, limit: int = 8) -> list[MemoryHit]:
        if not query.strip() or limit < 1:
            return []
        if before_episode is None:
            rows = self.db.fetch_all("SELECT * FROM memory_documents WHERE novel_id=?", (novel_id,))
        else:
            rows = self.db.fetch_all(
                "SELECT * FROM memory_documents WHERE novel_id=? AND episode<?", (novel_id, before_episode)
            )
        query_vector = self.embed(query)
        hits = [MemoryHit(row["episode"], row["source_type"], row["content"],
                          round(self.cosine(query_vector, json.loads(row["vector_json"])), 6)) for row in rows]
        hits = [hit for hit in hits if hit.score > 0]
        return sorted(hits, key=lambda hit: (-hit.score, -hit.episode))[:limit]

    def embed(self, text: str) -> dict[str, float]:
        tokens = [token.lower() for token in TOKEN_PATTERN.findall(text)]
        compact_korean = "".join(re.findall(r"[가-힣]", text))
        tokens.extend(compact_korean[index:index + 2] for index in range(max(0, len(compact_korean) - 1)))
        counts: Counter[int] = Counter(self._bucket(token) for token in tokens)
        norm = math.sqrt(sum(value * value for value in counts.values())) or 1.0
        return {str(index): round(value / norm, 8) for index, value in counts.items()}

    @staticmethod
    def cosine(left: dict[str, float], right: dict[str, float]) -> float:
        if len(left) > len(right):
            left, right = right, left
        return sum(value * right.get(index, 0.0) for index, value in left.items())

    def _bucket(self, token: str) -> int:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % self.dimensions

