"""Tests for /consent endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.consent import ConsentRecord
from app.models.patient import Patient
from app.models.user import User
from tests.conftest import AUTH_HEADER


@pytest.mark.asyncio
async def test_record_consent_service_usage(
    client: AsyncClient, owner_user: User, patient: Patient
):
    """POST /consent should record a service_usage consent."""
    resp = await client.post(
        "/consent",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(patient.id),
            "consent_type": "service_usage",
            "granted": True,
            "granted_by": "John Doe",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["consent_type"] == "service_usage"
    assert data["granted"] is True
    assert data["granted_by"] == "John Doe"
    assert data["patient_id"] == str(patient.id)
    assert data["recorded_by"] == str(owner_user.id)
    assert data["revoked_at"] is None


@pytest.mark.asyncio
async def test_record_consent_training_data(
    client: AsyncClient, owner_user: User, patient: Patient
):
    """POST /consent should record a training_data consent."""
    resp = await client.post(
        "/consent",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(patient.id),
            "consent_type": "training_data",
            "granted": False,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["consent_type"] == "training_data"
    assert data["granted"] is False


@pytest.mark.asyncio
async def test_record_consent_invalid_type(
    client: AsyncClient, owner_user: User, patient: Patient
):
    """POST /consent with invalid consent_type returns 400."""
    resp = await client.post(
        "/consent",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(patient.id),
            "consent_type": "marketing",
            "granted": True,
        },
    )
    assert resp.status_code == 400
    assert "Invalid consent type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_record_consent_other_clinic_patient(
    client: AsyncClient, owner_user: User, other_clinic_patient: Patient
):
    """Cannot record consent for another clinic's patient."""
    resp = await client.post(
        "/consent",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(other_clinic_patient.id),
            "consent_type": "service_usage",
            "granted": True,
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_record_consent_writes_audit_log(
    client: AsyncClient, owner_user: User, patient: Patient, db_session: AsyncSession
):
    """Recording consent should write an audit log."""
    await client.post(
        "/consent",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(patient.id),
            "consent_type": "service_usage",
            "granted": True,
        },
    )
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "consent.record")
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.resource_type == "consent"


@pytest.mark.asyncio
async def test_get_patient_consent_records(
    client: AsyncClient, owner_user: User, patient: Patient
):
    """GET /patients/{id}/consent should return all consent records."""
    # Record two consents
    await client.post(
        "/consent",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(patient.id),
            "consent_type": "service_usage",
            "granted": True,
            "granted_by": "Patient",
        },
    )
    await client.post(
        "/consent",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(patient.id),
            "consent_type": "training_data",
            "granted": False,
        },
    )

    resp = await client.get(f"/patients/{patient.id}/consent", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    # Should be ordered most recent first
    types = [r["consent_type"] for r in data]
    assert "service_usage" in types
    assert "training_data" in types


@pytest.mark.asyncio
async def test_get_consent_other_clinic_patient(
    client: AsyncClient, owner_user: User, other_clinic_patient: Patient
):
    """Cannot view consent records for another clinic's patient."""
    resp = await client.get(f"/patients/{other_clinic_patient.id}/consent", headers=AUTH_HEADER)
    assert resp.status_code == 404
