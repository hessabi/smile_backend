"""Tests for /patients endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.patient import Patient
from app.models.user import User
from tests.conftest import AUTH_HEADER


@pytest.mark.asyncio
async def test_create_patient(client: AsyncClient, owner_user: User, db_session: AsyncSession):
    """POST /patients should create a patient record in the current clinic."""
    resp = await client.post(
        "/patients",
        headers=AUTH_HEADER,
        json={
            "display_name": "Jane D.",
            "external_id": "PAT-002",
            "email": "jane@example.com",
            "phone": "+15125559999",
            "notes": "New patient",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["display_name"] == "Jane D."
    assert data["external_id"] == "PAT-002"
    assert data["email"] == "jane@example.com"
    assert data["phone"] == "+15125559999"
    assert data["notes"] == "New patient"
    assert data["clinic_id"] == str(owner_user.clinic_id)


@pytest.mark.asyncio
async def test_create_patient_minimal(client: AsyncClient, owner_user: User):
    """POST /patients with only required field (display_name)."""
    resp = await client.post(
        "/patients",
        headers=AUTH_HEADER,
        json={"display_name": "Min Patient"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["display_name"] == "Min Patient"
    assert data["external_id"] is None
    assert data["email"] is None
    assert data["phone"] is None


@pytest.mark.asyncio
async def test_create_patient_writes_audit_log(
    client: AsyncClient, owner_user: User, db_session: AsyncSession
):
    """Creating a patient should write an audit log."""
    await client.post(
        "/patients",
        headers=AUTH_HEADER,
        json={"display_name": "Audit Patient"},
    )
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "patient.create")
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.resource_type == "patient"


@pytest.mark.asyncio
async def test_list_patients(client: AsyncClient, owner_user: User, patient: Patient):
    """GET /patients should return patients for the current clinic."""
    resp = await client.get("/patients", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["patients"]) == 1
    assert data["patients"][0]["display_name"] == "John D."


@pytest.mark.asyncio
async def test_list_patients_search_by_name(client: AsyncClient, owner_user: User, patient: Patient):
    """GET /patients?search=john should match by display_name."""
    resp = await client.get("/patients?search=john", headers=AUTH_HEADER)
    data = resp.json()
    assert data["total"] == 1
    assert data["patients"][0]["display_name"] == "John D."

    # Search for non-existent name
    resp = await client.get("/patients?search=nonexistent", headers=AUTH_HEADER)
    data = resp.json()
    assert data["total"] == 0
    assert len(data["patients"]) == 0


@pytest.mark.asyncio
async def test_list_patients_search_by_external_id(client: AsyncClient, owner_user: User, patient: Patient):
    """GET /patients?search=PAT-001 should match by external_id."""
    resp = await client.get("/patients?search=PAT-001", headers=AUTH_HEADER)
    data = resp.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_patients_pagination(client: AsyncClient, owner_user: User, db_session: AsyncSession):
    """GET /patients with limit/offset should paginate correctly."""
    clinic_id = owner_user.clinic_id
    for i in range(5):
        db_session.add(Patient(clinic_id=clinic_id, display_name=f"Patient {i}"))
    await db_session.commit()

    resp = await client.get("/patients?limit=2&offset=0", headers=AUTH_HEADER)
    data = resp.json()
    assert data["total"] == 5
    assert len(data["patients"]) == 2

    resp = await client.get("/patients?limit=2&offset=4", headers=AUTH_HEADER)
    data = resp.json()
    assert len(data["patients"]) == 1


@pytest.mark.asyncio
async def test_get_patient_by_id(client: AsyncClient, owner_user: User, patient: Patient):
    """GET /patients/{id} should return the specific patient."""
    resp = await client.get(f"/patients/{patient.id}", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(patient.id)
    assert data["display_name"] == "John D."


@pytest.mark.asyncio
async def test_get_patient_from_other_clinic_returns_404(
    client: AsyncClient, owner_user: User, other_clinic_patient: Patient
):
    """Cannot access patients from another clinic."""
    resp = await client.get(f"/patients/{other_clinic_patient.id}", headers=AUTH_HEADER)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_patient(client: AsyncClient, owner_user: User, patient: Patient):
    """PUT /patients/{id} should update patient fields."""
    resp = await client.put(
        f"/patients/{patient.id}",
        headers=AUTH_HEADER,
        json={"display_name": "John Updated", "email": "newemail@example.com"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "John Updated"
    assert data["email"] == "newemail@example.com"
    # Unchanged fields should remain
    assert data["external_id"] == "PAT-001"
    assert data["phone"] == "+15125551234"


@pytest.mark.asyncio
async def test_update_patient_from_other_clinic_returns_404(
    client: AsyncClient, owner_user: User, other_clinic_patient: Patient
):
    """Cannot update patients from another clinic."""
    resp = await client.put(
        f"/patients/{other_clinic_patient.id}",
        headers=AUTH_HEADER,
        json={"display_name": "Hacked"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_patient_writes_audit_log(
    client: AsyncClient, owner_user: User, patient: Patient, db_session: AsyncSession
):
    """Updating a patient should write an audit log."""
    await client.put(
        f"/patients/{patient.id}",
        headers=AUTH_HEADER,
        json={"display_name": "Updated Name"},
    )
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "patient.update")
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.resource_id == patient.id
