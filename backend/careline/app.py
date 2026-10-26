from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.careline.config import ROOT_DIR, get_settings
from backend.careline.db import ClinicStore
from backend.careline.faq import DAY_ABBREVIATIONS, configured_faq
from backend.careline.voice.pipeline import run_voice_session

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

faq_path = ROOT_DIR / "clinic_faq.json"
faq_items = json.loads(faq_path.read_text(encoding="utf-8"))
store = ClinicStore(settings.db_path, settings)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    store.initialize(configured_faq(faq_items, settings))
    logging.getLogger("careline").info(
        "startup clinic_demo=true data_path=%s providers=%s/%s/%s",
        settings.db_path,
        settings.llm_provider,
        settings.stt_provider,
        settings.tts_provider,
    )
    yield


app = FastAPI(title="Careline Clinic Voice Receptionist", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse({"ok": True, "demo": True})


@app.get("/api/config")
async def public_config() -> JSONResponse:
    return JSONResponse(
        {
            "clinic_name": settings.clinic_name,
            "timezone": settings.clinic_timezone,
            "language": "en",
            "demo_only": True,
            "working_days": [DAY_ABBREVIATIONS[day] for day in settings.working_days],
            "open_time": settings.clinic_open_time,
            "close_time": settings.clinic_close_time,
            "lunch_start": settings.clinic_lunch_start,
            "lunch_end": settings.clinic_lunch_end,
            "appointment_minutes": settings.appointment_minutes,
        }
    )


@app.websocket("/ws")
async def voice_socket(websocket: WebSocket) -> None:
    try:
        await run_voice_session(websocket, settings, store)
    except WebSocketDisconnect:
        logging.getLogger("careline").info("voice_socket_disconnected")
    except Exception as exc:
        # Do not log exception contents: provider errors can contain request metadata.
        logging.getLogger("careline").error(
            "voice_session_failed error_type=%s", type(exc).__name__
        )
        try:
            await websocket.close(code=1011, reason="Voice session unavailable")
        except Exception:
            pass


web_dist = ROOT_DIR / "web" / "dist"
if web_dist.exists():
    app.mount("/assets", StaticFiles(directory=web_dist / "assets"), name="assets")


@app.get("/manus-routes.json", include_in_schema=False)
async def route_manifest() -> FileResponse:
    return FileResponse(ROOT_DIR / "web" / "public" / "manus-routes.json", media_type="application/json")


@app.get("/{path:path}", include_in_schema=False)
async def frontend(path: str = ""):
    if path.startswith("api/") or path == "ws":
        return JSONResponse({"detail": "Not found"}, status_code=404)
    web_root = web_dist.resolve()
    requested_file = (web_root / path).resolve()
    try:
        requested_file.relative_to(web_root)
    except ValueError:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    if requested_file.is_file():
        return FileResponse(requested_file)
    index_path = web_dist / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return JSONResponse(
        {
            "service": "Careline clinic voice receptionist",
            "status": "frontend_not_built",
            "hint": "Run npm --prefix web run build.",
        },
        status_code=503,
    )
