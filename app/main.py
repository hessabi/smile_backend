import logging
import os
from contextlib import asynccontextmanager

import firebase_admin
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings

logger = logging.getLogger(__name__)

_is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"


async def _seed_dev_data():
    """Seed a test clinic + user when ENVIRONMENT=test (dev bypass). Remove before production."""
    from sqlalchemy import select
    from app.database import async_session_factory
    from app.models.clinic import Clinic
    from app.models.user import User

    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.firebase_uid == "dev-user-uid"))
        if result.scalar_one_or_none():
            return  # already seeded

        import uuid
        from datetime import datetime, timedelta, timezone

        clinic_id = uuid.uuid4()
        clinic = Clinic(
            id=clinic_id,
            name="Dev Test Clinic",
            plan="trial",
            account_type="practice",
            is_active=True,
            subscription_status="trial",
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(clinic)

        user = User(
            id=uuid.uuid4(),
            clinic_id=clinic_id,
            firebase_uid="dev-user-uid",
            email="dev@smilepreview.test",
            name="Dev User",
            role="owner",
            is_active=True,
            is_platform_admin=True,
            email_verified=True,
        )
        db.add(user)
        await db.commit()
        logger.info("Seeded dev test clinic + user")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            options={"projectId": settings.firebase_project_id}
        )
        logger.info("Firebase Admin SDK initialized")

    # DEV BYPASS: seed test data (remove before production)
    _is_test = os.getenv("ENVIRONMENT", "development").lower() == "test"
    if _is_test:
        from app.database import engine, Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await _seed_dev_data()

    yield


app = FastAPI(
    title="SmilePreview API",
    lifespan=lifespan,
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
)


# L1/L4: Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        if _is_production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Custom OpenAPI schema with detailed docs
from app.core.openapi_schema import create_custom_openapi

app.openapi = create_custom_openapi(app)

# Custom docs routes with branded gate page
from app.core.docs import register_docs_routes

register_docs_routes(app)

# API routers
from app.routers import (
    admin,
    audit_logs,
    auth,
    clinics,
    consent,
    dental_schools,
    images,
    patients,
    post_procedure,
    share,
    simulations,
    subscription,
    team,
)

app.include_router(auth.router)
app.include_router(dental_schools.router)
app.include_router(clinics.router)
app.include_router(patients.router)
app.include_router(simulations.router)
app.include_router(images.router)
app.include_router(consent.router)
app.include_router(post_procedure.router)
app.include_router(share.router)
app.include_router(team.router)
app.include_router(subscription.router)
app.include_router(admin.router)
app.include_router(audit_logs.router)


# I1: Health check with DB ping
@app.get("/health", tags=["💚 Health"])
async def health():
    from app.database import engine

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return Response(
            content='{"status":"degraded","database":"unreachable"}',
            status_code=503,
            media_type="application/json",
        )
