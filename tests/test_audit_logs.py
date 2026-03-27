"""Tests for /audit-logs endpoint."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.clinic import Clinic
from app.models.user import User
from tests.conftest import AUTH_HEADER


@pytest.mark.asyncio
async def test_list_audit_logs_as_owner(
    client: AsyncClient, owner_user: User, db_session: AsyncSession, clinic: Clinic
):
    """GET /audit-logs should return audit entries for the current clinic."""
    # Seed some audit entries
    for i in range(3):
        db_session.add(
            AuditLog(
                clinic_id=clinic.id,
                user_id=owner_user.id,
                action=f"test.action_{i}",
                resource_type="test",
            )
        )
    await db_session.commit()

    resp = await client.get("/audit-logs", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["logs"]) == 3
    # Most recent first
    actions = [log["action"] for log in data["logs"]]
    assert "test.action_2" in actions


@pytest.mark.asyncio
async def test_audit_logs_pagination(
    client: AsyncClient, owner_user: User, db_session: AsyncSession, clinic: Clinic
):
    """GET /audit-logs with limit/offset should paginate."""
    for i in range(10):
        db_session.add(
            AuditLog(
                clinic_id=clinic.id,
                user_id=owner_user.id,
                action=f"bulk.action_{i}",
            )
        )
    await db_session.commit()

    resp = await client.get("/audit-logs?limit=3&offset=0", headers=AUTH_HEADER)
    data = resp.json()
    assert data["total"] == 10
    assert len(data["logs"]) == 3

    resp = await client.get("/audit-logs?limit=3&offset=9", headers=AUTH_HEADER)
    data = resp.json()
    assert len(data["logs"]) == 1


@pytest.mark.asyncio
async def test_audit_logs_provider_rejected(
    client: AsyncClient, provider_user: User, mock_firebase
):
    """Providers cannot access audit logs."""
    mock_firebase.verify_id_token.return_value = {"uid": "provider-firebase-uid"}
    resp = await client.get("/audit-logs", headers=AUTH_HEADER)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_audit_logs_nurse_rejected(
    client: AsyncClient, nurse_user: User, mock_firebase
):
    """Nurses cannot access audit logs."""
    mock_firebase.verify_id_token.return_value = {"uid": "nurse-firebase-uid"}
    resp = await client.get("/audit-logs", headers=AUTH_HEADER)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_audit_logs_office_admin_allowed(
    client: AsyncClient, db_session: AsyncSession, clinic: Clinic, subscription, mock_firebase
):
    """Office admins can access audit logs."""
    admin = User(
        clinic_id=clinic.id,
        firebase_uid="audit-admin-uid",
        email="auditadmin@test.com",
        name="Audit Admin",
        role="office_admin",
        email_verified=True,
    )
    db_session.add(admin)
    await db_session.commit()

    mock_firebase.verify_id_token.return_value = {"uid": "audit-admin-uid"}
    resp = await client.get("/audit-logs", headers=AUTH_HEADER)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_audit_logs_clinic_isolation(
    client: AsyncClient,
    owner_user: User,
    db_session: AsyncSession,
    clinic: Clinic,
    other_clinic: Clinic,
):
    """Audit logs from another clinic should not be visible."""
    # Add log for other clinic
    db_session.add(
        AuditLog(
            clinic_id=other_clinic.id,
            action="other.action",
            resource_type="test",
        )
    )
    # Add log for our clinic
    db_session.add(
        AuditLog(
            clinic_id=clinic.id,
            user_id=owner_user.id,
            action="our.action",
            resource_type="test",
        )
    )
    await db_session.commit()

    resp = await client.get("/audit-logs", headers=AUTH_HEADER)
    data = resp.json()
    assert data["total"] == 1
    assert data["logs"][0]["action"] == "our.action"


@pytest.mark.asyncio
async def test_audit_log_entry_fields(
    client: AsyncClient, owner_user: User, db_session: AsyncSession, clinic: Clinic
):
    """Verify audit log entries contain expected fields."""
    import uuid

    resource_id = uuid.uuid4()
    db_session.add(
        AuditLog(
            clinic_id=clinic.id,
            user_id=owner_user.id,
            action="patient.create",
            resource_type="patient",
            resource_id=resource_id,
            details={"display_name": "Test"},
            ip_address="127.0.0.1",
            user_agent="TestAgent/1.0",
        )
    )
    await db_session.commit()

    resp = await client.get("/audit-logs", headers=AUTH_HEADER)
    log = resp.json()["logs"][0]
    assert log["action"] == "patient.create"
    assert log["resource_type"] == "patient"
    assert log["resource_id"] == str(resource_id)
    assert log["details"]["display_name"] == "Test"
    assert log["ip_address"] == "127.0.0.1"
    assert log["user_agent"] == "TestAgent/1.0"
    assert log["user_id"] == str(owner_user.id)
    assert "created_at" in log
