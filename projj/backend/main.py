"""Main FastAPI application entry point."""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.v1 import profile, jobs, filters, telegram, ollama, scheduler
from backend.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# WebSocket connection pool
_ws_clients: Set[WebSocket] = set()


async def broadcast(message: dict):
    """Broadcast a message to all connected WebSocket clients."""
    if not _ws_clients:
        return
    dead = set()
    for ws in _ws_clients.copy():
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            dead.add(ws)
    _ws_clients -= dead


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting JobBot backend...")

    # Init DB
    from backend.migrations.init_db import init_db
    init_db()

    # Set broadcast callback on scrape worker
    from backend.workers.scrape_worker import set_broadcast
    set_broadcast(broadcast)

    # Start scheduler
    from backend.services.scheduler.job_scheduler import start_scheduler
    await start_scheduler()

    # Start application queue processor
    from backend.services.applier.applier_manager import process_queue
    asyncio.create_task(process_queue())

    # Try to start Telegram bot from saved config
    from backend.services.telegram.bot import try_start_from_db
    await try_start_from_db()

    logger.info(f"JobBot running at http://{settings.app_host}:{settings.app_port}")

    yield

    # Shutdown
    logger.info("Shutting down JobBot...")
    from backend.services.scheduler.job_scheduler import stop_scheduler
    from backend.services.telegram.bot import stop_bot
    from backend.services.scraper.scraper_manager import scraper_manager
    from backend.services.applier.applier_manager import stop_browser

    await stop_scheduler()
    await stop_bot()
    await scraper_manager.stop()
    await stop_browser()
    logger.info("Shutdown complete")


app = FastAPI(
    title="JobBot API",
    description="Automated job application platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(profile.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(filters.router, prefix="/api/v1")
app.include_router(telegram.router, prefix="/api/v1")
app.include_router(ollama.router, prefix="/api/v1")
app.include_router(scheduler.router, prefix="/api/v1")


@app.websocket("/ws/jobs")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.add(websocket)
    try:
        while True:
            # Keep connection alive
            await asyncio.wait_for(websocket.receive_text(), timeout=30)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        _ws_clients.discard(websocket)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# Serve React frontend (built files)
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(frontend_dist):
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        index = os.path.join(frontend_dist, "index.html")
        return FileResponse(index)
