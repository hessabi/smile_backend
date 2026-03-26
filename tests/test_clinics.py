"""Tests for /clinics endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.clinic import Clinic
from app.models.user import User
from tests.conftest import AUTH_HEADER


@pytest.mark.asyncio
async def test_get_clinic(client: AsyncClient, owner_user: User, clinic: Clinic):
    """GET /clinics/me should return the current user's clinic."""
    resp = await client.get("/clinics/me", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(clinic.id)
    assert data["name"] == "Test Dental Clinic"
    assert data["plan"] == "trial"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_update_clinic_name(
    client: AsyncClient, owner_user: User, clinic: Clinic, db_session: AsyncSession
):
    """PUT /clinics/me should update the clinic name."""
    resp = await client.put(
        "/clinics/me",
        headers=AUTH_HEADER,
        json={"name": "Updated Dental Clinic"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Dental Clinic"

    # Verify persisted in DB
    await db_session.refresh(clinic)
    # Check that the name was persisted (may need re-query since different session)
    result = await db_session.execute(select(Clinic).where(Clinic.id == clinic.id))
    refreshed = result.scalar_one()
    assert refreshed.name == "Updated Dental Clinic"


@pytest.mark.asyncio
async def test_update_clinic_settings(client: AsyncClient, owner_user: User, clinic: Clinic):
    """PUT /clinics/me should update the clinic settings JSON."""
    resp = await client.put(
        "/clinics/me",
        headers=AUTH_HEADER,
        json={"settings": {"default_shade": "natural", "branding_color": "#2563eb"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["settings"]["default_shade"] == "natural"
    assert data["settings"]["branding_color"] == "#2563eb"


@pytest.mark.asyncio
async def test_update_clinic_partial(client: AsyncClient, owner_user: User, clinic: Clinic):
    """Partial update: only changing name should not affect settings."""
    # First set settings
    await client.put(
        "/clinics/me",
        headers=AUTH_HEADER,
        json={"settings": {"key": "value"}},
    )
    # Then update only name
    resp = await client.put(
        "/clinics/me",
        headers=AUTH_HEADER,
        json={"name": "New Name Only"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New Name Only"
    # Settings should still have the key from the first update
    assert data["settings"]["key"] == "value"


@pytest.mark.asyncio
async def test_update_clinic_creates_audit_log(
    client: AsyncClient, owner_user: User, clinic: Clinic, db_session: AsyncSession
):
    """PUT /clinics/me should create an audit log entry."""
    await client.put(
        "/clinics/me",
        headers=AUTH_HEADER,
        json={"name": "Audit Test"},
    )
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "clinic.update")
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.clinic_id == clinic.id
    assert log.user_id == owner_user.id
    assert log.resource_type == "clinic"


@pytest.mark.asyncio
async def test_get_clinic_without_auth(client: AsyncClient):
    """GET /clinics/me without auth should fail."""
    resp = await client.get("/clinics/me")
    assert resp.status_code == 422
