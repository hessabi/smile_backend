"""Tests for /auth endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.clinic import Clinic
from app.models.user import User
from tests.conftest import AUTH_HEADER


@pytest.mark.asyncio
async def test_register_creates_clinic_and_owner(client: AsyncClient, db_session: AsyncSession):
    """Registration should verify Bearer token, create clinic + owner user."""
    resp = await client.post(
        "/auth/register",
        headers=AUTH_HEADER,
        json={
            "email": "dr.smith@example.com",
            "name": "Dr. Smith",
            "clinic_name": "Smith Dental",
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["user"]["email"] == "dr.smith@example.com"
    assert data["user"]["name"] == "Dr. Smith"
    assert data["user"]["role"] == "owner"
    assert data["user"]["is_active"] is True
    assert data["user"]["firebase_uid"] == "test-firebase-uid"

    assert data["clinic"]["name"] == "Smith Dental"
    assert data["clinic"]["plan"] == "trial"
    assert data["clinic"]["is_active"] is True
    assert data["user"]["clinic_id"] == data["clinic"]["id"]

    result = await db_session.execute(select(AuditLog))
    logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].action == "user.register"


@pytest.mark.asyncio
async def test_register_without_token_returns_422(client: AsyncClient):
    """Registration without Bearer token should fail."""
    resp = await client.post(
        "/auth/register",
        json={
            "email": "no-token@example.com",
            "name": "No Token",
            "clinic_name": "No Token Clinic",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_with_invalid_token_returns_401(client: AsyncClient, mock_firebase):
    """Registration with invalid token should return 401."""
    mock_firebase.verify_id_token.side_effect = Exception("Invalid token")
    resp = await client.post(
        "/auth/register",
        headers={"Authorization": "Bearer bad-token"},
        json={
            "email": "bad@example.com",
            "name": "Bad",
            "clinic_name": "Bad Clinic",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_duplicate_firebase_uid_rejected(client: AsyncClient, owner_user: User):
    """Cannot register the same Firebase UID twice."""
    resp = await client.post(
        "/auth/register",
        headers=AUTH_HEADER,
        json={
            "email": "duplicate@example.com",
            "name": "Duplicate",
            "clinic_name": "Dup Clinic",
        },
    )
    assert resp.status_code == 400
    assert "already registered" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_me_returns_current_user_and_clinic(client: AsyncClient, owner_user: User, clinic: Clinic):
    """GET /auth/me should return the authenticated user and their clinic."""
    resp = await client.get("/auth/me", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["id"] == str(owner_user.id)
    assert data["user"]["email"] == owner_user.email
    assert data["user"]["role"] == "owner"
    assert data["clinic"]["id"] == str(clinic.id)
    assert data["clinic"]["name"] == clinic.name


@pytest.mark.asyncio
async def test_me_without_auth_returns_422(client: AsyncClient):
    """GET /auth/me without Authorization header should return 422."""
    resp = await client.get("/auth/me")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_me_with_invalid_token_returns_401(client: AsyncClient, mock_firebase):
    """GET /auth/me with an invalid token should return 401."""
    mock_firebase.verify_id_token.side_effect = Exception("Invalid token")
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer bad-token"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_deactivated_user_returns_401(
    client: AsyncClient, db_session: AsyncSession, owner_user: User
):
    """Deactivated users should get 401 even with valid token."""
    owner_user.is_active = False
    db_session.add(owner_user)
    await db_session.commit()

    resp = await client.get("/auth/me", headers=AUTH_HEADER)
    assert resp.status_code == 401
    assert "deactivated" in resp.json()["detail"]
