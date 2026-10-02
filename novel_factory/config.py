from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_path: Path
    upload_dir: Path

    @classmethod
    def from_env(cls) -> "Settings":
        if os.getenv("NOVEL_FACTORY_DATA"):
            data_dir = Path(os.environ["NOVEL_FACTORY_DATA"]).resolve()
        elif sys.platform == "win32":
            data_dir = Path(os.getenv("LOCALAPPDATA", Path.home())) / "AI Novel Factory"
        else:
            data_dir = Path.home() / ".ai-novel-factory"
        return cls(
            data_dir=data_dir,
            database_path=data_dir / "novel_factory.db",
            upload_dir=data_dir / "uploads",
        )

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
