"""Tests for /team endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.clinic import Clinic
from app.models.user import User
from tests.conftest import AUTH_HEADER


@pytest.mark.asyncio
async def test_list_team(client: AsyncClient, owner_user: User):
    """GET /team should list all users in the clinic."""
    resp = await client.get("/team", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["email"] == owner_user.email
    assert data[0]["role"] == "owner"


@pytest.mark.asyncio
async def test_list_team_nurse_rejected(
    client: AsyncClient, nurse_user: User, mock_firebase
):
    """Nurses cannot access /team (requires owner or office_admin)."""
    mock_firebase.verify_id_token.return_value = {"uid": "nurse-firebase-uid"}
    resp = await client.get("/team", headers=AUTH_HEADER)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_team_provider_rejected(
    client: AsyncClient, provider_user: User, mock_firebase
):
    """Providers cannot access /team."""
    mock_firebase.verify_id_token.return_value = {"uid": "provider-firebase-uid"}
    resp = await client.get("/team", headers=AUTH_HEADER)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_invite_team_member(
    client: AsyncClient, owner_user: User, db_session: AsyncSession
):
    """POST /team/invite should create a new user in the clinic."""
    resp = await client.post(
        "/team/invite",
        headers=AUTH_HEADER,
        json={
            "email": "newdoc@testclinic.com",
            "name": "Dr. New",
            "role": "provider",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newdoc@testclinic.com"
    assert data["name"] == "Dr. New"
    assert data["role"] == "provider"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_invite_team_member_invalid_role(client: AsyncClient, owner_user: User):
    """POST /team/invite with invalid role returns 400."""
    resp = await client.post(
        "/team/invite",
        headers=AUTH_HEADER,
        json={
            "email": "bad@testclinic.com",
            "name": "Bad Role",
            "role": "superadmin",
        },
    )
    assert resp.status_code == 400
    assert "Invalid role" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_invite_team_member_duplicate_email(
    client: AsyncClient, owner_user: User
):
    """POST /team/invite with existing email returns 400."""
    # First invite
    await client.post(
        "/team/invite",
        headers=AUTH_HEADER,
        json={"email": "dup@testclinic.com", "name": "First", "role": "nurse"},
    )
    # Duplicate
    resp = await client.post(
        "/team/invite",
        headers=AUTH_HEADER,
        json={"email": "dup@testclinic.com", "name": "Second", "role": "nurse"},
    )
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_invite_owner_by_non_owner_rejected(
    client: AsyncClient, db_session: AsyncSession, clinic: Clinic, mock_firebase
):
    """Only owners can invite with the owner role."""
    # Create an office_admin user
    admin = User(
        clinic_id=clinic.id,
        firebase_uid="office-admin-uid",
        email="admin@testclinic.com",
        name="Office Admin",
        role="office_admin",
    )
    db_session.add(admin)
    await db_session.commit()

    mock_firebase.verify_id_token.return_value = {"uid": "office-admin-uid"}
    resp = await client.post(
        "/team/invite",
        headers=AUTH_HEADER,
        json={"email": "owner2@testclinic.com", "name": "New Owner", "role": "owner"},
    )
    assert resp.status_code == 403
    assert "Only owners" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_invite_owner_by_owner_allowed(client: AsyncClient, owner_user: User):
    """Owners can invite other owners."""
    resp = await client.post(
        "/team/invite",
        headers=AUTH_HEADER,
        json={"email": "owner2@testclinic.com", "name": "Co-Owner", "role": "owner"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "owner"


@pytest.mark.asyncio
async def test_invite_writes_audit_log(
    client: AsyncClient, owner_user: User, db_session: AsyncSession
):
    """Inviting a team member should write an audit log."""
    await client.post(
        "/team/invite",
        headers=AUTH_HEADER,
        json={"email": "audit@testclinic.com", "name": "Audit Nurse", "role": "nurse"},
    )
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "team.invite")
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.resource_type == "user"


@pytest.mark.asyncio
async def test_update_team_member_role(
    client: AsyncClient, owner_user: User, db_session: AsyncSession, clinic: Clinic
):
    """PUT /team/{user_id} should update the team member's role."""
    # Create a nurse to promote
    nurse = User(
        clinic_id=clinic.id,
        firebase_uid="promote-nurse-uid",
        email="promote@testclinic.com",
        name="Nurse Promote",
        role="nurse",
    )
    db_session.add(nurse)
    await db_session.commit()
    await db_session.refresh(nurse)

    resp = await client.put(
        f"/team/{nurse.id}",
        headers=AUTH_HEADER,
        json={"role": "office_admin"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "office_admin"


@pytest.mark.asyncio
async def test_deactivate_team_member(
    client: AsyncClient, owner_user: User, db_session: AsyncSession, clinic: Clinic
):
    """PUT /team/{user_id} with is_active=false should deactivate the user."""
    nurse = User(
        clinic_id=clinic.id,
        firebase_uid="deactivate-uid",
        email="deactivate@testclinic.com",
        name="Nurse Deactivate",
        role="nurse",
    )
    db_session.add(nurse)
    await db_session.commit()
    await db_session.refresh(nurse)

    resp = await client.put(
        f"/team/{nurse.id}",
        headers=AUTH_HEADER,
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_cannot_modify_self(client: AsyncClient, owner_user: User):
    """PUT /team/{user_id} should not allow modifying your own account."""
    resp = await client.put(
        f"/team/{owner_user.id}",
        headers=AUTH_HEADER,
        json={"role": "nurse"},
    )
    assert resp.status_code == 400
    assert "Cannot modify your own" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_user_from_other_clinic_returns_404(
    client: AsyncClient, owner_user: User, other_clinic_user: User
):
    """Cannot update users from another clinic."""
    resp = await client.put(
        f"/team/{other_clinic_user.id}",
        headers=AUTH_HEADER,
        json={"role": "nurse"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_non_owner_cannot_assign_owner_role(
    client: AsyncClient, db_session: AsyncSession, clinic: Clinic, mock_firebase
):
    """Office admin cannot assign owner role to someone."""
    admin = User(
        clinic_id=clinic.id,
        firebase_uid="admin-assign-uid",
        email="admin-assign@testclinic.com",
        name="Admin Assigner",
        role="office_admin",
    )
    nurse = User(
        clinic_id=clinic.id,
        firebase_uid="target-nurse-uid",
        email="target@testclinic.com",
        name="Target Nurse",
        role="nurse",
    )
    db_session.add_all([admin, nurse])
    await db_session.commit()
    await db_session.refresh(nurse)

    mock_firebase.verify_id_token.return_value = {"uid": "admin-assign-uid"}
    resp = await client.put(
        f"/team/{nurse.id}",
        headers=AUTH_HEADER,
        json={"role": "owner"},
    )
    assert resp.status_code == 403
    assert "Only owners" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_team_member_writes_audit_log(
    client: AsyncClient, owner_user: User, db_session: AsyncSession, clinic: Clinic
):
    """Updating a team member should write an audit log."""
    nurse = User(
        clinic_id=clinic.id,
        firebase_uid="audit-update-uid",
        email="audit-update@testclinic.com",
        name="Audit Update",
        role="nurse",
    )
    db_session.add(nurse)
    await db_session.commit()
    await db_session.refresh(nurse)

    await client.put(
        f"/team/{nurse.id}",
        headers=AUTH_HEADER,
        json={"role": "provider"},
    )
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "team.update")
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.resource_id == nurse.id
