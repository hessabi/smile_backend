"""Tests for /images endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.clinic import Clinic
from app.models.user import User
from tests.conftest import AUTH_HEADER


@pytest.mark.asyncio
async def test_get_upload_url_before(client: AsyncClient, owner_user: User):
    """POST /images/upload-url for a 'before' photo should return signed URL and key."""
    resp = await client.post(
        "/images/upload-url",
        headers=AUTH_HEADER,
        json={"content_type": "image/jpeg", "purpose": "before"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "upload_url" in data
    assert "image_key" in data
    assert data["upload_url"].startswith("https://")


@pytest.mark.asyncio
async def test_get_upload_url_post_procedure(client: AsyncClient, owner_user: User):
    """POST /images/upload-url for 'post_procedure' purpose."""
    resp = await client.post(
        "/images/upload-url",
        headers=AUTH_HEADER,
        json={"content_type": "image/png", "purpose": "post_procedure"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "upload_url" in data
    assert "image_key" in data


@pytest.mark.asyncio
async def test_get_upload_url_invalid_purpose(client: AsyncClient, owner_user: User):
    """POST /images/upload-url with invalid purpose returns 400."""
    resp = await client.post(
        "/images/upload-url",
        headers=AUTH_HEADER,
        json={"content_type": "image/jpeg", "purpose": "avatar"},
    )
    assert resp.status_code == 400
    assert "Invalid purpose" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_upload_url_invalid_content_type(client: AsyncClient, owner_user: User):
    """POST /images/upload-url with invalid content type returns 400."""
    resp = await client.post(
        "/images/upload-url",
        headers=AUTH_HEADER,
        json={"content_type": "application/pdf", "purpose": "before"},
    )
    assert resp.status_code == 400
    assert "Invalid content type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_upload_url_writes_audit_log(
    client: AsyncClient, owner_user: User, db_session: AsyncSession
):
    """POST /images/upload-url should write an audit log."""
    await client.post(
        "/images/upload-url",
        headers=AUTH_HEADER,
        json={"content_type": "image/jpeg", "purpose": "before"},
    )
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "image.upload_url_generated")
    )
    log = result.scalar_one_or_none()
    assert log is not None


@pytest.mark.asyncio
async def test_get_download_url(client: AsyncClient, owner_user: User, clinic: Clinic):
    """GET /images/{key} should return a signed download URL."""
    image_key = f"clinics/{clinic.id}/before/test.jpg"
    resp = await client.get(f"/images/{image_key}", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert "download_url" in data
    assert data["download_url"].startswith("https://")


@pytest.mark.asyncio
async def test_get_download_url_cross_clinic_rejected(
    client: AsyncClient, owner_user: User, other_clinic: Clinic
):
    """GET /images/{key} with another clinic's image key returns 403."""
    image_key = f"clinics/{other_clinic.id}/before/stolen.jpg"
    resp = await client.get(f"/images/{image_key}", headers=AUTH_HEADER)
    assert resp.status_code == 403
    assert "Access denied" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_download_url_writes_audit_log(
    client: AsyncClient, owner_user: User, clinic: Clinic, db_session: AsyncSession
):
    """GET /images/{key} should write an audit log."""
    image_key = f"clinics/{clinic.id}/before/test.jpg"
    await client.get(f"/images/{image_key}", headers=AUTH_HEADER)
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "image.download_url_generated")
    )
    log = result.scalar_one_or_none()
    assert log is not None
