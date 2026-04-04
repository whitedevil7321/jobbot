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

from backend.api.v1 import profile, jobs, filters, telegram, ollama, scheduler, email_config, extension
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
    _ws_clients.difference_update(dead)  # in-place remove — avoids UnboundLocalError


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
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"chrome-extension://.*|moz-extension://.*",
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
app.include_router(email_config.router, prefix="/api/v1")
app.include_router(extension.router, prefix="/api/v1")


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

    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        index = os.path.join(frontend_dist, "index.html")
        return FileResponse(index)
else:
    from fastapi.responses import HTMLResponse

    @app.get("/{full_path:path}")
    async def frontend_not_built(full_path: str):
        return HTMLResponse("""
<!DOCTYPE html><html><head><title>JobBot</title>
<style>body{font-family:system-ui;background:#0a0a0f;color:#e2e8f0;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}
.box{background:#111827;border:1px solid #1f2937;border-radius:12px;padding:40px;max-width:480px;text-align:center;}
h1{color:#8b5cf6;margin:0 0 8px;}code{background:#1f2937;padding:2px 8px;border-radius:4px;color:#a78bfa;}
.step{text-align:left;margin:16px 0;padding:12px;background:#1f2937;border-radius:8px;font-size:14px;}
</style></head><body><div class="box">
<h1>⚡ JobBot</h1>
<p style="color:#9ca3af;margin:0 0 24px">Backend is running! Frontend needs to be built.</p>
<div class="step">1. Open a new terminal in the project folder</div>
<div class="step">2. Run: <code>cd frontend</code></div>
<div class="step">3. Run: <code>npm install</code></div>
<div class="step">4. Run: <code>npm run build</code></div>
<div class="step">5. Restart: <code>start.bat</code></div>
<p style="margin-top:24px;color:#6b7280;font-size:13px">API is available at <code>/api/v1</code> · Health: <code>/api/health</code></p>
</div></body></html>""", status_code=200)
