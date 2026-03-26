"""Tests for /patients/{id}/post-procedure endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.clinic import Clinic
from app.models.patient import Patient
from app.models.simulation import Simulation
from app.models.user import User
from tests.conftest import AUTH_HEADER


@pytest.mark.asyncio
async def test_create_post_procedure(
    client: AsyncClient, owner_user: User, patient: Patient, clinic: Clinic
):
    """POST /patients/{id}/post-procedure should create a post-procedure record."""
    image_key = f"clinics/{clinic.id}/post-procedure/photo.jpg"
    resp = await client.post(
        f"/patients/{patient.id}/post-procedure",
        headers=AUTH_HEADER,
        json={
            "image_key": image_key,
            "procedure_date": "2026-04-15",
            "notes": "Veneers placed, patient happy",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["patient_id"] == str(patient.id)
    assert data["image_key"] == image_key
    assert data["procedure_date"] == "2026-04-15"
    assert data["notes"] == "Veneers placed, patient happy"
    assert data["uploaded_by"] == str(owner_user.id)
    assert data["image_url"] is not None


@pytest.mark.asyncio
async def test_create_post_procedure_with_simulation(
    client: AsyncClient,
    owner_user: User,
    patient: Patient,
    clinic: Clinic,
    completed_simulation: Simulation,
):
    """POST /patients/{id}/post-procedure can be linked to a simulation."""
    image_key = f"clinics/{clinic.id}/post-procedure/linked.jpg"
    resp = await client.post(
        f"/patients/{patient.id}/post-procedure",
        headers=AUTH_HEADER,
        json={
            "image_key": image_key,
            "simulation_id": str(completed_simulation.id),
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["simulation_id"] == str(completed_simulation.id)


@pytest.mark.asyncio
async def test_create_post_procedure_cross_clinic_image_rejected(
    client: AsyncClient, owner_user: User, patient: Patient, other_clinic: Clinic
):
    """Cannot create post-procedure with image key from another clinic."""
    image_key = f"clinics/{other_clinic.id}/post-procedure/stolen.jpg"
    resp = await client.post(
        f"/patients/{patient.id}/post-procedure",
        headers=AUTH_HEADER,
        json={"image_key": image_key},
    )
    assert resp.status_code == 403
    assert "Invalid image key" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_post_procedure_other_clinic_patient(
    client: AsyncClient, owner_user: User, other_clinic_patient: Patient, clinic: Clinic
):
    """Cannot create post-procedure for another clinic's patient."""
    resp = await client.post(
        f"/patients/{other_clinic_patient.id}/post-procedure",
        headers=AUTH_HEADER,
        json={"image_key": f"clinics/{clinic.id}/post-procedure/x.jpg"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_post_procedure_writes_audit_log(
    client: AsyncClient, owner_user: User, patient: Patient, clinic: Clinic, db_session: AsyncSession
):
    """Creating a post-procedure record should write an audit log."""
    await client.post(
        f"/patients/{patient.id}/post-procedure",
        headers=AUTH_HEADER,
        json={"image_key": f"clinics/{clinic.id}/post-procedure/audit.jpg"},
    )
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "post_procedure.create")
    )
    log = result.scalar_one_or_none()
    assert log is not None


@pytest.mark.asyncio
async def test_list_post_procedure(
    client: AsyncClient, owner_user: User, patient: Patient, clinic: Clinic
):
    """GET /patients/{id}/post-procedure should list all post-procedure images."""
    # Create two post-procedure records
    for i in range(2):
        await client.post(
            f"/patients/{patient.id}/post-procedure",
            headers=AUTH_HEADER,
            json={"image_key": f"clinics/{clinic.id}/post-procedure/photo{i}.jpg"},
        )

    resp = await client.get(f"/patients/{patient.id}/post-procedure", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    for record in data:
        assert record["patient_id"] == str(patient.id)
        assert record["image_url"] is not None


@pytest.mark.asyncio
async def test_list_post_procedure_other_clinic_patient(
    client: AsyncClient, owner_user: User, other_clinic_patient: Patient
):
    """Cannot list post-procedure for another clinic's patient."""
    resp = await client.get(
        f"/patients/{other_clinic_patient.id}/post-procedure",
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 404
