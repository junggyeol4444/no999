from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS reference_works (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, filename TEXT NOT NULL,
  source_format TEXT NOT NULL, status TEXT NOT NULL, raw_path TEXT NOT NULL,
  profile_json TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS novels (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, genre TEXT NOT NULL,
  premise TEXT NOT NULL, target_episodes INTEGER NOT NULL,
  characters_per_episode INTEGER NOT NULL, atmosphere TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'PLANNING', bible_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS novel_references (
  novel_id TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  reference_id TEXT NOT NULL REFERENCES reference_works(id) ON DELETE CASCADE,
  weights_json TEXT NOT NULL, PRIMARY KEY (novel_id, reference_id)
);
CREATE TABLE IF NOT EXISTS characters (
  id TEXT PRIMARY KEY, novel_id TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  data_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS timeline (
  id TEXT PRIMARY KEY, novel_id TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  episode INTEGER NOT NULL, occurred_at TEXT NOT NULL, description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS relationships (
  id TEXT PRIMARY KEY, novel_id TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  source_character_id TEXT NOT NULL, target_character_id TEXT NOT NULL,
  episode INTEGER NOT NULL, state TEXT NOT NULL, description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS foreshadowing (
  id TEXT PRIMARY KEY, novel_id TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  setup_episode INTEGER NOT NULL, description TEXT NOT NULL,
  planned_payoff INTEGER, status TEXT NOT NULL DEFAULT 'OPEN'
);
CREATE TABLE IF NOT EXISTS episodes (
  id TEXT PRIMARY KEY, novel_id TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  number INTEGER NOT NULL, title TEXT NOT NULL, outline_json TEXT NOT NULL,
  draft TEXT NOT NULL DEFAULT '', final_text TEXT NOT NULL DEFAULT '',
  summary_json TEXT NOT NULL DEFAULT '{}', quality_json TEXT,
  status TEXT NOT NULL DEFAULT 'PLANNED', UNIQUE(novel_id, number)
);
CREATE TABLE IF NOT EXISTS generation_jobs (
  id TEXT PRIMARY KEY, novel_id TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  start_episode INTEGER NOT NULL, end_episode INTEGER NOT NULL, next_episode INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'QUEUED', completed_count INTEGER NOT NULL DEFAULT 0,
  error TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS memory_documents (
  id TEXT PRIMARY KEY, novel_id TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  episode INTEGER NOT NULL, source_type TEXT NOT NULL, content TEXT NOT NULL,
  vector_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(novel_id, episode, source_type)
);
CREATE INDEX IF NOT EXISTS idx_memory_documents_novel_episode
  ON memory_documents(novel_id, episode);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> None:
        with self.connect() as connection:
            connection.execute(query, params)

    def fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(query, params).fetchone()
        return dict(row) if row else None

    def fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)
