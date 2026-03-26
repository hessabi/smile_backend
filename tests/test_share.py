"""Tests for share endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.share_token import ShareToken
from app.models.simulation import Simulation
from app.models.user import User
from tests.conftest import AUTH_HEADER


@pytest.mark.asyncio
async def test_create_share_link(
    client: AsyncClient, owner_user: User, completed_simulation: Simulation
):
    """POST /simulations/{id}/share should create a share token and return a URL."""
    resp = await client.post(
        f"/simulations/{completed_simulation.id}/share",
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "share_url" in data
    assert "expires_at" in data
    assert "id" in data
    assert "/share/" in data["share_url"]


@pytest.mark.asyncio
async def test_create_share_link_failed_simulation(
    client: AsyncClient, owner_user: User, failed_simulation: Simulation
):
    """Cannot share a failed simulation."""
    resp = await client.post(
        f"/simulations/{failed_simulation.id}/share",
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 400
    assert "completed" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_share_link_writes_audit_log(
    client: AsyncClient,
    owner_user: User,
    completed_simulation: Simulation,
    db_session: AsyncSession,
):
    """Creating a share link should write an audit log."""
    await client.post(
        f"/simulations/{completed_simulation.id}/share",
        headers=AUTH_HEADER,
    )
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "share.create")
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.resource_type == "share_token"


@pytest.mark.asyncio
async def test_view_shared_simulation(
    client: AsyncClient, share_token: ShareToken, completed_simulation: Simulation
):
    """GET /share/{token} should return public simulation data without auth."""
    resp = await client.get(f"/share/{share_token.token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["clinic_name"] == "Test Dental Clinic"
    assert data["provider_name"] == "Dr. Test Owner"
    assert data["treatment_type"] == "veneers"
    assert data["shade"] == "natural"
    assert data["before_image_url"] is not None
    assert data["preview_image_url"] is not None
    assert "disclaimer" in data
    assert "AI-generated" in data["disclaimer"]


@pytest.mark.asyncio
async def test_view_shared_simulation_no_auth_required(
    client: AsyncClient, share_token: ShareToken
):
    """GET /share/{token} should work without any Authorization header."""
    resp = await client.get(f"/share/{share_token.token}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_view_shared_simulation_expired(
    client: AsyncClient, expired_share_token: ShareToken
):
    """GET /share/{token} with expired token should return 410."""
    resp = await client.get(f"/share/{expired_share_token.token}")
    assert resp.status_code == 410
    assert "expired" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_view_shared_simulation_invalid_token(client: AsyncClient):
    """GET /share/{token} with nonexistent token should return 404."""
    resp = await client.get("/share/totally-fake-token-that-doesnt-exist")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_multiple_share_links_for_same_simulation(
    client: AsyncClient, owner_user: User, completed_simulation: Simulation
):
    """Can create multiple share links for the same simulation."""
    resp1 = await client.post(
        f"/simulations/{completed_simulation.id}/share",
        headers=AUTH_HEADER,
    )
    resp2 = await client.post(
        f"/simulations/{completed_simulation.id}/share",
        headers=AUTH_HEADER,
    )
    assert resp1.status_code == 201
    assert resp2.status_code == 201
    # URLs should be different (different tokens)
    assert resp1.json()["share_url"] != resp2.json()["share_url"]
