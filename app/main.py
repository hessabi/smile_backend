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


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            options={"projectId": settings.firebase_project_id}
        )
        logger.info("Firebase Admin SDK initialized")
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
