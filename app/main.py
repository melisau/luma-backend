from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.api.events import router as events_router
from app.api.photos import router as photos_router
from app.core.config import get_settings
from app.core.security import generate_event_token, hash_password, mask_token
from app.db.database import SessionLocal, init_db
from app.db.models import AdminUser, Event

logger = logging.getLogger(__name__)

PRIVATE_HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Robots-Tag": "noindex, nofollow, noimageindex",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}


def seed_database() -> None:
    settings = get_settings()
    db: Session = SessionLocal()
    try:
        if not db.query(AdminUser).first():
            db.add(
                AdminUser(
                    email=settings.admin_email.lower(),
                    password_hash=hash_password(settings.admin_password),
                )
            )

        if not db.query(Event).first():
            token = settings.seed_event_token or generate_event_token()
            db.add(
                Event(
                    name=settings.seed_event_name,
                    slug="melisa-berk",
                    private_token=token,
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
    init_db()
    seed_database()
    yield


app = FastAPI(title="Luma Planner API", version="0.2.0", lifespan=lifespan)
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Event-Token"],
)

app.include_router(events_router, prefix="/api")
app.include_router(photos_router, prefix="/api")

frontend_dir = settings.resolved_frontend_path
if frontend_dir:
    mount_frontend(app, frontend_dir)


@app.middleware("http")
async def privacy_headers_middleware(request: Request, call_next):
    response = await call_next(request)
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
    payload = {"status": "ok", "frontend": bool(frontend_dir)}
    if frontend_dir:
        payload["frontend_path"] = str(frontend_dir)
    return payload


@app.get("/robots.txt")
def robots_txt():
    if frontend_dir and (frontend_dir / "robots.txt").is_file():
        return FileResponse(frontend_dir / "robots.txt", media_type="text/plain")
    content = "User-agent: *\nDisallow: /api/\n"
    return JSONResponse(content=content, media_type="text/plain")
