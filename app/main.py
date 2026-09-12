import asyncio
from starlette.concurrency import run_in_threadpool
from app.api.event_access import router as access_router, require_event_access
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import uuid
import time

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.event_data import router as event_data_router
from app.api.events import router as events_router
from app.api.photos import router as photos_router
from app.core.config import get_settings
from app.core.security import generate_event_token, hash_password, mask_token
from app.db import database as db_module
from app.db.database import init_db
from app.db.models import AdminUser, Event

logger = logging.getLogger(__name__)
if get_settings().sentry_dsn:
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=get_settings().sentry_dsn,environment=get_settings().environment,send_default_pii=False)
    except ImportError:
        logger.warning("SENTRY_DSN ayarlı ancak sentry-sdk kurulu değil")

PRIVATE_HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Robots-Tag": "noindex, nofollow, noimageindex",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}


def seed_database() -> None:
    settings = get_settings()
    db: Session = db_module.SessionLocal()
    try:
        admin = db.query(AdminUser).filter(AdminUser.email == settings.admin_email.lower()).one_or_none()
        if not admin:
            admin = AdminUser(
                email=settings.admin_email.lower(),
                password_hash=hash_password(settings.admin_password),
            )
            db.add(admin)
            db.flush()

        if not db.query(Event).filter(Event.admin_id == admin.id).first():
            token = settings.seed_event_token or generate_event_token()
            db.add(
                Event(
                    admin_id=admin.id,
                    name=settings.seed_event_name,
                    slug="ornek-etkinlik",
                    private_token=token,
                    event_date=datetime(2026, 9, 6, 15, 30, tzinfo=timezone.utc),
                )
            )
            db.commit()
            logger.info("Seed event created with token prefix %s", mask_token(token))
        else:
            db.commit()
    finally:
        db.close()


def mount_frontend(app: FastAPI, frontend_dir) -> None:
    @app.get("/e/{event_token}")
    def public_invitation(event_token: str):
        return FileResponse(frontend_dir / "index.html", headers=PRIVATE_HEADERS)

    @app.get("/e/{event_token}/upload")
    def public_upload_invitation(event_token: str):
        return FileResponse(frontend_dir / "index.html", headers=PRIVATE_HEADERS)

    @app.get("/")
    def admin_panel():
        return FileResponse(frontend_dir / "index.html")

    app.mount("/assets", StaticFiles(directory=frontend_dir / "assets"), name="assets")
    app.mount("/css", StaticFiles(directory=frontend_dir / "css"), name="css")
    app.mount("/js", StaticFiles(directory=frontend_dir / "js"), name="js")
    logger.info("Frontend served from %s", frontend_dir)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings().validate_production()
    init_db()
    seed_database()
    async def cleanup_loop():
        from app.services.memory_retention import purge_expired_memories
        while True:
            await asyncio.sleep(max(60,get_settings().memory_cleanup_interval_seconds))
            try:
                result=await run_in_threadpool(purge_expired_memories)
                if any(result.values()):logger.info('Expired memories removed: %s',result)
            except Exception:logger.exception('Memory cleanup cycle failed; will retry')
    async def reminder_loop():
        from app.services.reminder_service import send_due_reminders
        while True:
            await asyncio.sleep(60)
            try: await run_in_threadpool(send_due_reminders)
            except Exception: logger.exception('RSVP reminder cycle failed; will retry')
    task=asyncio.create_task(cleanup_loop()) if get_settings().memory_cleanup_enabled else None
    reminder_task=asyncio.create_task(reminder_loop())
    try:
        yield
    finally:
        if task:
            task.cancel()
            try:await task
            except asyncio.CancelledError:pass
        reminder_task.cancel()
        try: await reminder_task
        except asyncio.CancelledError: pass


app = FastAPI(title="Luma Planner API", version="0.2.0", lifespan=lifespan)
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Event-Token"],
)

app.include_router(events_router, prefix="/api", dependencies=[Depends(require_event_access)])
app.include_router(photos_router, prefix="/api", dependencies=[Depends(require_event_access)])
app.include_router(event_data_router, prefix="/api", dependencies=[Depends(require_event_access)])

app.include_router(access_router, prefix="/api")

frontend_dir = settings.resolved_frontend_path
if frontend_dir:
    mount_frontend(app, frontend_dir)


@app.middleware("http")
async def privacy_headers_middleware(request: Request, call_next):
    request_id=request.headers.get("X-Request-ID") or str(uuid.uuid4());started=time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"]=request_id
    logger.info("request method=%s path=%s status=%s duration_ms=%.1f request_id=%s",request.method,request.url.path,response.status_code,(time.perf_counter()-started)*1000,request_id)
    if request.url.path.startswith(("/e/", "/api/")):
        for key, value in PRIVATE_HEADERS.items():
            response.headers.setdefault(key, value)
    return response


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin."},
    )


@app.get("/health")
def health():
    payload: dict[str, str | bool] = {
        "status": "ok",
        "frontend": bool(frontend_dir),
    }
    if frontend_dir:
        payload["frontend_path"] = str(frontend_dir)

    db = db_module.SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        payload["database"] = "ok"
    except Exception:
        logger.exception("Health check database probe failed")
        payload["status"] = "degraded"
        payload["database"] = "error"
        return JSONResponse(status_code=503, content=payload)
    finally:
        db.close()

    settings = get_settings()
    try:
        if settings.storage_backend == "local":
            storage_path = settings.local_storage_path.expanduser()
            storage_path.mkdir(parents=True, exist_ok=True)
            payload["storage"] = "ok" if storage_path.is_dir() else "error"
        elif settings.storage_bucket and settings.storage_access_key_id:
            payload["storage"] = "configured"
        else:
            payload["storage"] = "error"
    except Exception:
        logger.exception("Health check storage probe failed")
        payload["storage"] = "error"

    if payload.get("storage") == "error":
        payload["status"] = "degraded"
        return JSONResponse(status_code=503, content=payload)

    return payload


@app.get("/robots.txt")
def robots_txt():
    if frontend_dir and (frontend_dir / "robots.txt").is_file():
        return FileResponse(frontend_dir / "robots.txt", media_type="text/plain")
    content = "User-agent: *\nDisallow: /api/\n"
    return JSONResponse(content=content, media_type="text/plain")
