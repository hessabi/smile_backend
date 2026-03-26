"""Tests for /admin platform admin endpoints."""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic import Clinic
from app.models.patient import Patient
from app.models.simulation import Simulation
from app.models.user import User
from tests.conftest import AUTH_HEADER


@pytest.mark.asyncio
async def test_admin_list_clinics(
    client: AsyncClient, platform_admin: User, clinic: Clinic
):
    """Platform admin can list all clinics."""
    resp = await client.get("/admin/clinics", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    clinic_data = data["clinics"][0]
    assert "user_count" in clinic_data
    assert "patient_count" in clinic_data
    assert "simulation_count" in clinic_data
    assert "subscription_status" in clinic_data


@pytest.mark.asyncio
async def test_admin_list_clinics_non_admin_rejected(
    client: AsyncClient, owner_user: User
):
    """Non-platform-admin users cannot access admin endpoints."""
    resp = await client.get("/admin/clinics", headers=AUTH_HEADER)
    assert resp.status_code == 403
    assert "Platform admin" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_list_clinics_search(
    client: AsyncClient, platform_admin: User, db_session: AsyncSession
):
    """Platform admin can search clinics by name."""
    other = Clinic(name="Unique Smile Studio")
    db_session.add(other)
    await db_session.commit()

    resp = await client.get("/admin/clinics?search=Unique", headers=AUTH_HEADER)
    data = resp.json()
    assert data["total"] == 1
    assert data["clinics"][0]["name"] == "Unique Smile Studio"


@pytest.mark.asyncio
async def test_admin_get_clinic_detail(
    client: AsyncClient, platform_admin: User, clinic: Clinic, patient: Patient
):
    """Platform admin can get clinic detail with counts."""
    resp = await client.get(f"/admin/clinics/{clinic.id}", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == clinic.name
    assert data["patient_count"] >= 1
    assert data["user_count"] >= 1


@pytest.mark.asyncio
async def test_admin_list_users_cross_clinic(
    client: AsyncClient,
    platform_admin: User,
    clinic: Clinic,
    other_clinic: Clinic,
    other_clinic_user: User,
):
    """Platform admin can see users from ALL clinics."""
    resp = await client.get("/admin/users", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    clinic_ids = {u["clinic_id"] for u in data["users"]}
    assert str(clinic.id) in clinic_ids
    assert str(other_clinic.id) in clinic_ids
    for u in data["users"]:
        assert "clinic_name" in u


@pytest.mark.asyncio
async def test_admin_list_users_search(
    client: AsyncClient, platform_admin: User, db_session: AsyncSession, clinic: Clinic
):
    """Platform admin can search users by name or email."""
    target = User(
        clinic_id=clinic.id,
        firebase_uid="target-search-uid",
        email="findme@testclinic.com",
        name="Dr. Findable",
        role="provider",
    )
    db_session.add(target)
    await db_session.commit()

    resp = await client.get("/admin/users?search=findme", headers=AUTH_HEADER)
    data = resp.json()
    assert data["total"] == 1
    assert data["users"][0]["email"] == "findme@testclinic.com"


@pytest.mark.asyncio
async def test_admin_list_patients_cross_clinic(
    client: AsyncClient,
    platform_admin: User,
    patient: Patient,
    other_clinic_patient: Patient,
):
    """Platform admin can see patients from ALL clinics."""
    resp = await client.get("/admin/patients", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    patient_ids = {p["id"] for p in data["patients"]}
    assert str(patient.id) in patient_ids
    assert str(other_clinic_patient.id) in patient_ids


@pytest.mark.asyncio
async def test_admin_get_patient_detail_with_simulations(
    client: AsyncClient,
    platform_admin: User,
    clinic: Clinic,
    patient: Patient,
    db_session: AsyncSession,
):
    """Platform admin can see a patient's detail with all simulations and signed URLs."""
    sim = Simulation(
        clinic_id=clinic.id,
        patient_id=patient.id,
        created_by=platform_admin.id,
        treatment_type="veneers",
        shade="natural",
        before_image_key=f"clinics/{clinic.id}/before/test.jpg",
        result_image_key=f"clinics/{clinic.id}/results/test.jpg",
        status="completed",
        generation_time_ms=18000,
    )
    db_session.add(sim)
    await db_session.commit()

    resp = await client.get(f"/admin/patients/{patient.id}", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == patient.display_name
    assert data["clinic_name"] == clinic.name
    assert len(data["simulations"]) >= 1
    s = data["simulations"][0]
    assert s["before_image_url"] is not None
    assert s["result_image_url"] is not None


@pytest.mark.asyncio
async def test_admin_get_patient_not_found(
    client: AsyncClient, platform_admin: User
):
    """Platform admin gets 404 for nonexistent patient."""
    resp = await client.get(f"/admin/patients/{uuid.uuid4()}", headers=AUTH_HEADER)
    assert resp.status_code == 404
