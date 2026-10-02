from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import Settings
from .database import Database
from .services import NovelFactory


class NovelCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    genre: str = Field(min_length=1, max_length=80)
    premise: str = Field(min_length=10)
    target_episodes: int = Field(ge=1, le=2000)
    characters_per_episode: int = Field(default=5000, ge=500, le=30000)
    atmosphere: str = ""
    core_material: list[str] = []
    point_of_view: str = "3인칭 제한"
    target_audience: str = "웹소설 독자"
    ending: str = ""


class ReferenceLink(BaseModel):
    reference_id: str
    weights: dict[str, float]


class CharacterCreate(BaseModel):
    name: str
    age: int | None = None
    job: str = ""
    personality: list[str] = []
    speech_style: str = ""
    knowledge: list[str] = []
    relationships: dict[str, str] = {}
    goals: list[str] = []
    secrets: list[str] = []


class ForeshadowingCreate(BaseModel):
    setup_episode: int = Field(ge=1)
    description: str = Field(min_length=1)
    planned_payoff: int | None = Field(default=None, ge=1)


class TimelineCreate(BaseModel):
    episode: int = Field(ge=1)
    occurred_at: str
    description: str = Field(min_length=1)


class RelationshipCreate(BaseModel):
    source_character_id: str
    target_character_id: str
    episode: int = Field(ge=1)
    state: str = Field(min_length=1)
    description: str = ""


class EpisodePlan(BaseModel):
    title: str = ""
    purpose: str = Field(min_length=1)
    required_events: list[str] = []
    characters: list[str] = []
    emotion_flow: list[str] = []
    foreshadowing: list[str] = []
    reward: str = ""
    conflict: str = ""
    hook: str = ""
    scenes: list[dict[str, Any]] = []


class Manuscript(BaseModel):
    text: str = Field(min_length=1)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.ensure_directories()
    factory = NovelFactory(Database(settings.database_path), settings.upload_dir)
    app = FastAPI(title="AI Novel Factory", version="0.1.0", description="장편소설 분석·기획·기억·검수 API")
    app.state.factory = factory
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    def call(operation):
        try:
            return operation()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "ai-novel-factory"}

    @app.post("/api/references", status_code=201)
    async def register_reference(title: str = Form(...), file: UploadFile = File(...)):
        suffix = Path(file.filename or "reference.txt").suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
            shutil.copyfileobj(file.file, temporary)
            temporary_path = Path(temporary.name)
        try:
            return call(lambda: factory.register_reference(title, temporary_path))
        finally:
            temporary_path.unlink(missing_ok=True)

    @app.get("/api/references")
    def list_references():
        return factory.list_references()

    @app.post("/api/references/{reference_id}/analyze")
    def analyze_reference(reference_id: str):
        return call(lambda: factory.analyze_reference(reference_id))

    @app.post("/api/novels", status_code=201)
    def create_novel(payload: NovelCreate):
        return call(lambda: factory.create_novel(payload.model_dump()))

    @app.get("/api/novels")
    def list_novels():
        return factory.list_novels()

    @app.get("/api/novels/{novel_id}")
    def get_novel(novel_id: str):
        return call(lambda: factory.get_novel(novel_id))

    @app.post("/api/novels/{novel_id}/references", status_code=204)
    def link_reference(novel_id: str, payload: ReferenceLink):
        return call(lambda: factory.link_reference(novel_id, payload.reference_id, payload.weights))

    @app.post("/api/novels/{novel_id}/characters", status_code=201)
    def add_character(novel_id: str, payload: CharacterCreate):
        return call(lambda: factory.add_character(novel_id, payload.model_dump()))

    @app.post("/api/novels/{novel_id}/foreshadowing", status_code=201)
    def add_foreshadowing(novel_id: str, payload: ForeshadowingCreate):
        return call(lambda: factory.add_foreshadowing(novel_id, payload.model_dump()))

    @app.post("/api/novels/{novel_id}/timeline", status_code=201)
    def add_timeline_event(novel_id: str, payload: TimelineCreate):
        return call(lambda: factory.add_timeline_event(novel_id, payload.model_dump()))

    @app.post("/api/novels/{novel_id}/relationships", status_code=201)
    def add_relationship(novel_id: str, payload: RelationshipCreate):
        return call(lambda: factory.add_relationship(novel_id, payload.model_dump()))

    @app.post("/api/novels/{novel_id}/episodes/{number}/plan", status_code=201)
    def plan_episode(novel_id: str, number: int, payload: EpisodePlan):
        return call(lambda: factory.plan_episode(novel_id, number, payload.model_dump()))

    @app.put("/api/novels/{novel_id}/episodes/{number}/finalize")
    def finalize_episode(novel_id: str, number: int, payload: Manuscript):
        return call(lambda: factory.finalize_episode(novel_id, number, payload.text))

    @app.get("/api/novels/{novel_id}/episodes/{number}/context")
    def memory_context(novel_id: str, number: int):
        return call(lambda: factory.memory_context(novel_id, number))

    web_root = Path(__file__).resolve().parent.parent
    if (web_root / "index.html").exists():
        app.mount("/", StaticFiles(directory=web_root, html=True), name="frontend")
    return app


app = create_app()
