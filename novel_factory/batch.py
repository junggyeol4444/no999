from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from .orchestrator import EpisodeOrchestrator
from .services import NovelFactory


BatchProgress = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class BatchResult:
    job: dict[str, Any]
    generated: list[int]
    skipped: list[int]


class BatchGenerator:
    """Durable, resumable sequential episode generation worker."""

    def __init__(self, factory: NovelFactory, orchestrator: EpisodeOrchestrator):
        self.factory = factory
        self.orchestrator = orchestrator
        self._cancel = threading.Event()

    def create_job(self, novel_id: str, start_episode: int, end_episode: int) -> dict[str, Any]:
        novel = self.factory.get_novel(novel_id)
        if start_episode < 1 or end_episode < start_episode:
            raise ValueError("연속 생성 회차 범위가 올바르지 않습니다.")
        if end_episode > novel["target_episodes"]:
            raise ValueError("종료 회차가 작품의 목표 회차를 초과합니다.")
        active = self.factory.db.fetch_one(
            "SELECT id FROM generation_jobs WHERE novel_id=? AND status IN ('QUEUED','RUNNING','CANCELLING')", (novel_id,)
        )
        if active:
            raise ValueError("이 작품에 이미 실행 중이거나 대기 중인 연속 생성 작업이 있습니다.")
        job_id = f"JOB_{uuid.uuid4().hex[:12]}"
        self.factory.db.execute(
            "INSERT INTO generation_jobs(id,novel_id,start_episode,end_episode,next_episode) VALUES(?,?,?,?,?)",
            (job_id, novel_id, start_episode, end_episode, start_episode),
        )
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict[str, Any]:
        job = self.factory.db.fetch_one("SELECT * FROM generation_jobs WHERE id=?", (job_id,))
        if not job:
            raise KeyError(f"연속 생성 작업을 찾을 수 없습니다: {job_id}")
        return job

    def list_jobs(self, novel_id: str | None = None) -> list[dict[str, Any]]:
        if novel_id:
            return self.factory.db.fetch_all("SELECT * FROM generation_jobs WHERE novel_id=? ORDER BY created_at DESC", (novel_id,))
        return self.factory.db.fetch_all("SELECT * FROM generation_jobs ORDER BY created_at DESC")

    def cancel(self, job_id: str) -> None:
        job = self.get_job(job_id)
        if job["status"] not in {"QUEUED", "RUNNING"}:
            raise ValueError("대기 또는 실행 중인 작업만 중지할 수 있습니다.")
        self._cancel.set()
        self.factory.db.execute(
            "UPDATE generation_jobs SET status='CANCELLING',updated_at=CURRENT_TIMESTAMP WHERE id=?", (job_id,)
        )

    def run(self, job_id: str, progress: BatchProgress | None = None) -> BatchResult:
        notify = progress or (lambda _event: None)
        job = self.get_job(job_id)
        if job["status"] not in {"QUEUED", "FAILED", "CANCELLED"}:
            raise ValueError(f"실행할 수 없는 작업 상태입니다: {job['status']}")
        self._cancel.clear()
        self.factory.db.execute(
            "UPDATE generation_jobs SET status='RUNNING',error=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?", (job_id,)
        )
        generated: list[int] = []
        skipped: list[int] = []
        try:
            for number in range(job["next_episode"], job["end_episode"] + 1):
                if self._cancel.is_set():
                    self.factory.db.execute(
                        "UPDATE generation_jobs SET status='CANCELLED',next_episode=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (number, job_id),
                    )
                    final = self.get_job(job_id)
                    notify({"job": final, "episode": number, "stage": "cancelled", "percent": self._percent(final)})
                    return BatchResult(final, generated, skipped)
                existing = self.factory.db.fetch_one(
                    "SELECT status FROM episodes WHERE novel_id=? AND number=?", (job["novel_id"], number)
                )
                if existing and existing["status"] == "FINAL":
                    skipped.append(number)
                else:
                    notify({"job": self.get_job(job_id), "episode": number, "stage": "generating", "percent": self._percent(self.get_job(job_id))})
                    result = self.orchestrator.generate_episode(job["novel_id"], number)
                    if result.episode["status"] != "FINAL":
                        raise RuntimeError(f"{number}화가 품질 검사를 통과하지 못했습니다.")
                    generated.append(number)
                self.factory.db.execute(
                    "UPDATE generation_jobs SET next_episode=?,completed_count=completed_count+1,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (number + 1, job_id),
                )
                current = self.get_job(job_id)
                notify({"job": current, "episode": number, "stage": "completed", "percent": self._percent(current)})
            self.factory.db.execute(
                "UPDATE generation_jobs SET status='COMPLETED',updated_at=CURRENT_TIMESTAMP WHERE id=?", (job_id,)
            )
        except Exception as exc:
            self.factory.db.execute(
                "UPDATE generation_jobs SET status='FAILED',error=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (f"{type(exc).__name__}: {exc}"[:1000], job_id),
            )
            notify({"job": self.get_job(job_id), "stage": "failed", "error": str(exc), "percent": self._percent(self.get_job(job_id))})
            raise
        final = self.get_job(job_id)
        notify({"job": final, "stage": "finished", "percent": 100})
        return BatchResult(final, generated, skipped)

    @staticmethod
    def _percent(job: dict[str, Any]) -> int:
        total = job["end_episode"] - job["start_episode"] + 1
        return round(job["completed_count"] / total * 100) if total else 0

