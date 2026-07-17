"""
Novel Read Server - Main Entry Point

This module initializes and starts the Novel Read server application.
It exposes a FastAPI application with endpoints for managing novels,
chapters, rankings, source rules, search, AI-powered script generation,
and authentication.
"""

import base64
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func

from server.ai import CaptchaSolver, CodeModel, VisionModel
from server.channels import OfficialChannel, OpenSourceChannel, SearchChannel
from server.core.auth import auth_manager
from server.core.config import settings
from server.core.database import (
    Chapter,
    Novel,
    Ranking,
    SourceRule,
    get_db,
    init_db,
)


# ---------------------------------------------------------------------------
# Component singletons
# ---------------------------------------------------------------------------

def _build_code_model() -> CodeModel:
    cfg = settings.ai_code_model
    return CodeModel(endpoint=cfg.endpoint, model=cfg.model, api_key=cfg.api_key)


def _build_vision_model() -> VisionModel:
    cfg = settings.ai_vision_model
    return VisionModel(endpoint=cfg.endpoint, model=cfg.model, api_key=cfg.api_key)


# Lazily-instantiated components. They are created once on first use so that
# importing the module (e.g. for tests) does not require live credentials.
_code_model: Optional[CodeModel] = None
_vision_model: Optional[VisionModel] = None
_captcha_solver: Optional[CaptchaSolver] = None
_official_channel: Optional[OfficialChannel] = None
_search_channel: Optional[SearchChannel] = None
_opensource_channel: Optional[OpenSourceChannel] = None


def get_code_model() -> CodeModel:
    global _code_model
    if _code_model is None:
        _code_model = _build_code_model()
    return _code_model


def get_vision_model() -> VisionModel:
    global _vision_model
    if _vision_model is None:
        _vision_model = _build_vision_model()
    return _vision_model


def get_captcha_solver() -> CaptchaSolver:
    global _captcha_solver
    if _captcha_solver is None:
        _captcha_solver = CaptchaSolver(vision_model=get_vision_model())
    return _captcha_solver


def get_official_channel() -> OfficialChannel:
    global _official_channel
    if _official_channel is None:
        _official_channel = OfficialChannel()
    return _official_channel


def get_search_channel() -> SearchChannel:
    global _search_channel
    if _search_channel is None:
        _search_channel = SearchChannel()
    return _search_channel


def get_opensource_channel() -> OpenSourceChannel:
    global _opensource_channel
    if _opensource_channel is None:
        _opensource_channel = OpenSourceChannel()
    return _opensource_channel


# ---------------------------------------------------------------------------
# Lifespan / startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: create data dirs and initialize the database."""
    logger.info("Starting Novel Read Server...")

    # Ensure data directories exist
    for path in ("./data", "./logs", "./keys"):
        Path(path).mkdir(parents=True, exist_ok=True)

    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

    yield

    logger.info("Shutting down Novel Read Server...")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Novel Read API",
    description="Multi-platform novel reader backend (official, search, "
                "open-source channels + AI services).",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class NovelCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    author: str = Field("", max_length=200)
    description: Optional[str] = None
    cover_url: Optional[str] = None
    source: str = "manual"
    source_id: Optional[str] = None
    status: str = "ongoing"
    chapters_count: int = 0


class NovelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: Optional[str] = None
    description: Optional[str] = None
    cover_url: Optional[str] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    status: str
    chapters_count: int
    created_at: datetime
    updated_at: datetime


class ChapterCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    chapter_number: int = 0
    source_url: Optional[str] = None


class ChapterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    novel_id: int
    title: str
    chapter_number: int
    source_url: Optional[str] = None
    created_at: datetime


class ChapterDetail(ChapterOut):
    content: str


class SourceRuleCreate(BaseModel):
    domain: str = Field(..., min_length=1, max_length=200)
    name: Optional[str] = None
    rules_json: str = "{}"
    is_active: bool = True
    created_by: str = "manual"


class SourceRuleOut(SourceRuleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class RankingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source: Optional[str] = None
    type: Optional[str] = None
    novels: str
    updated_at: datetime


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""
    engine: str = ""


class TokenRequest(BaseModel):
    api_key: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ScriptGenRequest(BaseModel):
    url: str
    html_sample: str = ""
    requirements: str = "Extract novel title, author, chapter list and chapter content."


class ScriptFixRequest(BaseModel):
    script: str
    error_message: str
    context: str = ""


class ImageAnalyzeRequest(BaseModel):
    image_base64: str
    prompt: str = "Describe this image in detail."


class CaptchaRequest(BaseModel):
    image_base64: str
    captcha_type: str = "text"


class StatusResponse(BaseModel):
    status: str
    detail: Optional[str] = None


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str = Depends(_api_key_header)) -> str:
    """Dependency that validates the X-API-Key header against the configured key."""
    if not api_key or not auth_manager.verify_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key (X-API-Key header).",
        )
    return api_key


# ---------------------------------------------------------------------------
# Health & info
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"], response_model=StatusResponse)
async def health():
    """Liveness probe."""
    return {"status": "ok", "detail": "Novel Read server is running"}


@app.get("/api/info", tags=["system"], response_model=dict)
async def info():
    """Return basic server information."""
    return {
        "name": "Novel Read API",
        "version": app.version,
        "channels": {
            "official": settings.official_channel.enabled,
            "search": settings.search_channel.enabled,
            "opensource": True,
        },
        "ai": {
            "code_model": settings.ai_code_model.model,
            "vision_model": settings.ai_vision_model.model,
            "code_model_configured": settings.ai_code_model.api_key is not None,
            "vision_model_configured": settings.ai_vision_model.api_key is not None,
        },
        "p2p_enabled": settings.p2p.enabled,
    }


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.post("/api/auth/token", tags=["auth"], response_model=TokenResponse)
async def create_token(req: TokenRequest):
    """Exchange a server-side API key for a JWT access token."""
    if not auth_manager.verify_api_key(req.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )
    token = auth_manager.create_access_token({"sub": "api_client"})
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_hours * 3600,
    )


@app.get("/api/auth/verify", tags=["auth"], response_model=dict)
async def verify_token(token: str = Query(...)):
    """Verify a JWT token."""
    payload = auth_manager.decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )
    return {"valid": True, "payload": payload}


# ---------------------------------------------------------------------------
# Novels
# ---------------------------------------------------------------------------

@app.get("/api/novels", tags=["novels"], response_model=List[NovelOut])
async def list_novels(
    q: Optional[str] = Query(None, description="Search title/author"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
):
    """List novels, optionally filtered by a search query."""
    stmt = select(Novel).offset(offset).limit(limit).order_by(Novel.id.desc())
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Novel.title.like(like)) | (Novel.author.like(like)))
    result = await db.execute(stmt)
    return result.scalars().all()


@app.get("/api/novels/{novel_id}", tags=["novels"], response_model=NovelOut)
async def get_novel(novel_id: int, db=Depends(get_db)):
    novel = await db.get(Novel, novel_id)
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    return novel


@app.post(
    "/api/novels",
    tags=["novels"],
    response_model=NovelOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
async def create_novel(payload: NovelCreate, db=Depends(get_db)):
    novel = Novel(**payload.model_dump())
    db.add(novel)
    await db.commit()
    await db.refresh(novel)
    logger.info(f"Created novel id={novel.id} title={novel.title!r}")
    return novel


@app.delete(
    "/api/novels/{novel_id}",
    tags=["novels"],
    response_model=StatusResponse,
    dependencies=[Depends(require_api_key)],
)
async def delete_novel(novel_id: int, db=Depends(get_db)):
    novel = await db.get(Novel, novel_id)
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    await db.delete(novel)
    await db.commit()
    return {"status": "deleted", "detail": f"Novel {novel_id} removed"}


# ---------------------------------------------------------------------------
# Chapters
# ---------------------------------------------------------------------------

@app.get(
    "/api/novels/{novel_id}/chapters",
    tags=["chapters"],
    response_model=List[ChapterOut],
)
async def list_chapters(novel_id: int, db=Depends(get_db)):
    novel = await db.get(Novel, novel_id)
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    result = await db.execute(
        select(Chapter)
        .where(Chapter.novel_id == novel_id)
        .order_by(Chapter.chapter_number.asc())
    )
    return result.scalars().all()


@app.get("/api/chapters/{chapter_id}", tags=["chapters"], response_model=ChapterDetail)
async def get_chapter(chapter_id: int, db=Depends(get_db)):
    chapter = await db.get(Chapter, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapter


@app.post(
    "/api/novels/{novel_id}/chapters",
    tags=["chapters"],
    response_model=ChapterDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
async def add_chapter(novel_id: int, payload: ChapterCreate, db=Depends(get_db)):
    novel = await db.get(Novel, novel_id)
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    chapter = Chapter(novel_id=novel_id, **payload.model_dump())
    db.add(chapter)
    # Keep chapters_count in sync
    novel.chapters_count = (novel.chapters_count or 0) + 1
    await db.commit()
    await db.refresh(chapter)
    return chapter


# ---------------------------------------------------------------------------
# Source rules
# ---------------------------------------------------------------------------

@app.get("/api/rules", tags=["rules"], response_model=List[SourceRuleOut])
async def list_rules(active: Optional[bool] = Query(None), db=Depends(get_db)):
    stmt = select(SourceRule).order_by(SourceRule.id.desc())
    if active is not None:
        stmt = stmt.where(SourceRule.is_active == active)
    result = await db.execute(stmt)
    return result.scalars().all()


@app.post(
    "/api/rules",
    tags=["rules"],
    response_model=SourceRuleOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
async def create_rule(payload: SourceRuleCreate, db=Depends(get_db)):
    rule = SourceRule(**payload.model_dump())
    db.add(rule)
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create rule: {e}")
    await db.refresh(rule)
    return rule


# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------

@app.get("/api/rankings", tags=["rankings"], response_model=List[RankingOut])
async def list_rankings(db=Depends(get_db)):
    result = await db.execute(select(Ranking).order_by(Ranking.id.desc()))
    return result.scalars().all()


@app.get("/api/rankings/fetch", tags=["rankings"], response_model=List[dict])
async def fetch_rankings(source: str = Query("tomato")):
    """Fetch a live ranking list from the official channel (best-effort)."""
    channel = get_official_channel()
    rankings = await channel.fetch_rankings(source=source)
    return rankings


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@app.get("/api/search", tags=["search"], response_model=List[SearchResult])
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    engines: Optional[str] = Query(
        None, description="Comma-separated list of engines (baidu,bing,so360)"
    ),
):
    """Search across multiple engines for novel content."""
    if not settings.search_channel.enabled:
        raise HTTPException(status_code=503, detail="Search channel is disabled")
    engine_list = engines.split(",") if engines else None
    channel = get_search_channel()
    results = await channel.search(q, engines=engine_list)
    return results


@app.get("/api/search/opensource", tags=["search"], response_model=List[SearchResult])
async def search_opensource(q: str = Query(..., min_length=1)):
    """Search across configured open-source API endpoints."""
    channel = get_opensource_channel()
    results = await channel.search(q)
    # Normalize to SearchResult shape
    return [
        SearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=r.get("author", ""),
            engine=r.get("source", "opensource"),
        )
        for r in results
    ]


# ---------------------------------------------------------------------------
# AI endpoints
# ---------------------------------------------------------------------------

@app.post("/api/ai/generate-script", tags=["ai"], response_model=dict)
async def ai_generate_script(req: ScriptGenRequest):
    """Generate a web scraping script for a target URL via the code model."""
    model = get_code_model()
    script = await model.generate_scraping_script(
        url=req.url,
        html_sample=req.html_sample,
        requirements=req.requirements,
    )
    return {"script": script, "model_configured": model.client is not None}


@app.post("/api/ai/fix-script", tags=["ai"], response_model=dict)
async def ai_fix_script(req: ScriptFixRequest):
    """Attempt to fix a broken scraping script via the code model."""
    model = get_code_model()
    fixed = await model.fix_script_error(
        script=req.script,
        error_message=req.error_message,
        context=req.context,
    )
    return {"script": fixed, "model_configured": model.client is not None}


@app.post("/api/ai/analyze-image", tags=["ai"], response_model=dict)
async def ai_analyze_image(req: ImageAnalyzeRequest):
    """Analyze an image (base64-encoded) via the vision model."""
    try:
        image_data = base64.b64decode(req.image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")
    model = get_vision_model()
    description = await model.analyze_image(image_data, prompt=req.prompt)
    return {"description": description, "model_configured": model.client is not None}


@app.post("/api/ai/captcha", tags=["ai"], response_model=dict)
async def ai_solve_captcha(req: CaptchaRequest):
    """Solve a captcha image (base64-encoded) via the captcha solver."""
    try:
        image_data = base64.b64decode(req.image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")
    solver = get_captcha_solver()
    solution = await solver.solve(image_data, captcha_type=req.captcha_type)
    return solution


@app.get("/api/ai/status", tags=["ai"], response_model=dict)
async def ai_status():
    """Report AI component configuration status (no credentials leaked)."""
    return {
        "code_model": {
            "model": settings.ai_code_model.model,
            "endpoint": settings.ai_code_model.endpoint,
            "configured": settings.ai_code_model.api_key is not None,
        },
        "vision_model": {
            "model": settings.ai_vision_model.model,
            "endpoint": settings.ai_vision_model.endpoint,
            "configured": settings.ai_vision_model.api_key is not None,
        },
        "captcha_solved_total": get_captcha_solver().solved_count,
    }


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------

@app.get("/api/stats", tags=["system"], response_model=dict)
async def stats(db=Depends(get_db)):
    """Return aggregate counts of stored entities."""
    novel_count = await db.scalar(select(func.count(Novel.id)))
    chapter_count = await db.scalar(select(func.count(Chapter.id)))
    rule_count = await db.scalar(select(func.count(SourceRule.id)))
    ranking_count = await db.scalar(select(func.count(Ranking.id)))
    return {
        "novels": novel_count or 0,
        "chapters": chapter_count or 0,
        "rules": rule_count or 0,
        "rankings": ranking_count or 0,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Main entry point for the server."""
    logger.info(f"Configuration loaded from: {settings.config_file}")
    logger.info(f"Database: {settings.database_url}")
    logger.info(f"Listen on {settings.server_host}:{settings.server_port}")

    uvicorn.run(
        "server.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug",
    )


if __name__ == "__main__":
    main()
