from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_path: Path
    upload_dir: Path

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("NOVEL_FACTORY_DATA", "data")).resolve()
        return cls(
            data_dir=data_dir,
            database_path=data_dir / "novel_factory.db",
            upload_dir=data_dir / "uploads",
        )

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

