import logging, os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from .config import get_settings
from .db import Base, engine, SessionLocal
from .models import User
from .routers import auth, jobs, candidates, admin
from .security import hash_password

log = logging.getLogger("ats")


_initialized = False

def ensure_initialized():
    global _initialized
    if _initialized:
        return
    s = get_settings()
    Base.metadata.create_all(engine)
    os.makedirs(s.storage_dir, exist_ok=True)
    with SessionLocal() as db:
        admin_user = db.scalar(select(User).where(User.email == s.admin_email.lower()))
        if not admin_user:
            db.add(User(email=s.admin_email.lower(), name="Administrator", role="admin", password_hash=hash_password(s.admin_password)))
            db.commit()
            log.warning("Seeded initial admin %s", s.admin_email)
        else:
            admin_user.password_hash = hash_password(s.admin_password)
            admin_user.is_active = True
            admin_user.role = "admin"
            db.commit()
    _initialized = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_initialized()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="AI ATS", version="1.0.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def init_middleware(request: Request, call_next):
        ensure_initialized()
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
                             "Cache-Control": "no-store"})
        return resp

    @app.exception_handler(RequestValidationError)
    async def validation(_: Request, exc: RequestValidationError):
        errs = [{"field": ".".join(str(x) for x in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": "Validation failed", "errors": errs})

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    for r in (auth.router, jobs.router, candidates.router, admin.router):
        app.include_router(r)
    return app


app = create_app()
