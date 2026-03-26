"""Tests for /simulations endpoints."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.clinic import Clinic
from app.models.patient import Patient
from app.models.post_procedure import PostProcedureImage
from app.models.simulation import Simulation
from app.models.user import User
from app.services.gemini import GeminiResult
from tests.conftest import AUTH_HEADER


@pytest.mark.asyncio
async def test_create_simulation_success(
    client: AsyncClient, owner_user: User, patient: Patient, clinic: Clinic
):
    """POST /simulations should create a simulation and call the AI API."""
    before_key = f"clinics/{clinic.id}/before/test-photo.jpg"
    resp = await client.post(
        "/simulations",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(patient.id),
            "before_image_key": before_key,
            "treatment_type": "veneers",
            "shade": "natural",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"
    assert data["treatment_type"] == "veneers"
    assert data["shade"] == "natural"
    assert data["patient_id"] == str(patient.id)
    assert data["created_by"] == str(owner_user.id)
    assert data["before_image_url"] is not None
    assert data["result_image_url"] is not None
    assert data["generation_time_ms"] == 15000
    assert data["error_message"] is None


@pytest.mark.asyncio
async def test_create_simulation_invalid_treatment_type(
    client: AsyncClient, owner_user: User, patient: Patient, clinic: Clinic
):
    """POST /simulations with invalid treatment type returns 400."""
    resp = await client.post(
        "/simulations",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(patient.id),
            "before_image_key": f"clinics/{clinic.id}/before/test.jpg",
            "treatment_type": "invisalign",
            "shade": "natural",
        },
    )
    assert resp.status_code == 400
    assert "Invalid treatment type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_simulation_invalid_shade(
    client: AsyncClient, owner_user: User, patient: Patient, clinic: Clinic
):
    """POST /simulations with invalid shade returns 400."""
    resp = await client.post(
        "/simulations",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(patient.id),
            "before_image_key": f"clinics/{clinic.id}/before/test.jpg",
            "treatment_type": "veneers",
            "shade": "ultra-bright",
        },
    )
    assert resp.status_code == 400
    assert "Invalid shade" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_simulation_patient_from_other_clinic(
    client: AsyncClient, owner_user: User, other_clinic_patient: Patient, clinic: Clinic
):
    """Cannot create simulation for a patient from another clinic."""
    resp = await client.post(
        "/simulations",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(other_clinic_patient.id),
            "before_image_key": f"clinics/{clinic.id}/before/test.jpg",
            "treatment_type": "veneers",
            "shade": "natural",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_simulation_cross_clinic_image_key_rejected(
    client: AsyncClient, owner_user: User, patient: Patient, other_clinic: Clinic
):
    """Image key from another clinic should be rejected with 403."""
    resp = await client.post(
        "/simulations",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(patient.id),
            "before_image_key": f"clinics/{other_clinic.id}/before/stolen.jpg",
            "treatment_type": "veneers",
            "shade": "natural",
        },
    )
    assert resp.status_code == 403
    assert "Invalid image key" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_simulation_ai_failure(
    client: AsyncClient, owner_user: User, patient: Patient, clinic: Clinic, mock_gemini
):
    """When AI API fails, simulation should be saved with status=failed."""
    mock_gemini.return_value = GeminiResult(
        image_bytes=None,
        error="Service temporarily busy. Please try again.",
        elapsed_ms=5000,
        prompt="test",
    )
    resp = await client.post(
        "/simulations",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(patient.id),
            "before_image_key": f"clinics/{clinic.id}/before/test.jpg",
            "treatment_type": "veneers",
            "shade": "natural",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "failed"
    assert "busy" in data["error_message"]


@pytest.mark.asyncio
async def test_create_simulation_writes_audit_logs(
    client: AsyncClient, owner_user: User, patient: Patient, clinic: Clinic, db_session: AsyncSession
):
    """Creating a simulation should write create and complete audit logs."""
    await client.post(
        "/simulations",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(patient.id),
            "before_image_key": f"clinics/{clinic.id}/before/test.jpg",
            "treatment_type": "veneers",
            "shade": "natural",
        },
    )
    result = await db_session.execute(select(AuditLog).order_by(AuditLog.created_at))
    logs = result.scalars().all()
    actions = [log.action for log in logs]
    assert "simulation.create" in actions
    assert "simulation.complete" in actions


@pytest.mark.asyncio
async def test_get_simulation(
    client: AsyncClient, owner_user: User, completed_simulation: Simulation
):
    """GET /simulations/{id} should return the simulation with signed URLs."""
    resp = await client.get(f"/simulations/{completed_simulation.id}", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(completed_simulation.id)
    assert data["status"] == "completed"
    assert data["before_image_url"] is not None
    assert data["result_image_url"] is not None


@pytest.mark.asyncio
async def test_get_simulation_not_found(client: AsyncClient, owner_user: User):
    """GET /simulations/{id} for nonexistent ID returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/simulations/{fake_id}", headers=AUTH_HEADER)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_simulation_full_with_post_procedure(
    client: AsyncClient,
    owner_user: User,
    completed_simulation: Simulation,
    db_session: AsyncSession,
    clinic: Clinic,
    patient: Patient,
):
    """GET /simulations/{id}/full should include post-procedure image URL."""
    # Create a post-procedure image linked to the simulation
    pp = PostProcedureImage(
        clinic_id=clinic.id,
        patient_id=patient.id,
        simulation_id=completed_simulation.id,
        uploaded_by=owner_user.id,
        image_key=f"clinics/{clinic.id}/post-procedure/test.jpg",
    )
    db_session.add(pp)
    await db_session.commit()

    resp = await client.get(f"/simulations/{completed_simulation.id}/full", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["post_procedure_image_url"] is not None


@pytest.mark.asyncio
async def test_get_simulation_full_without_post_procedure(
    client: AsyncClient, owner_user: User, completed_simulation: Simulation
):
    """GET /simulations/{id}/full without post-op should have null post_procedure_image_url."""
    resp = await client.get(f"/simulations/{completed_simulation.id}/full", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["post_procedure_image_url"] is None


@pytest.mark.asyncio
async def test_get_simulation_pdf(
    client: AsyncClient, owner_user: User, completed_simulation: Simulation
):
    """GET /simulations/{id}/pdf should return PDF binary."""
    resp = await client.get(f"/simulations/{completed_simulation.id}/pdf", headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert b"PDF" in resp.content or b"pdf" in resp.content


@pytest.mark.asyncio
async def test_get_simulation_pdf_failed_simulation(
    client: AsyncClient, owner_user: User, failed_simulation: Simulation
):
    """GET /simulations/{id}/pdf for a failed simulation should return 400."""
    resp = await client.get(f"/simulations/{failed_simulation.id}/pdf", headers=AUTH_HEADER)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_patient_simulations(
    client: AsyncClient, owner_user: User, patient: Patient, completed_simulation: Simulation
):
    """GET /patients/{id}/simulations should list simulations for the patient."""
    resp = await client.get(f"/patients/{patient.id}/simulations", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["patient_id"] == str(patient.id)


@pytest.mark.asyncio
async def test_list_patient_simulations_pagination(
    client: AsyncClient, owner_user: User, patient: Patient, completed_simulation: Simulation
):
    """GET /patients/{id}/simulations with limit/offset should paginate."""
    resp = await client.get(
        f"/patients/{patient.id}/simulations?limit=1&offset=0",
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) <= 1


@pytest.mark.asyncio
async def test_list_patient_simulations_other_clinic_patient(
    client: AsyncClient, owner_user: User, other_clinic_patient: Patient
):
    """Cannot list simulations for a patient from another clinic."""
    resp = await client.get(f"/patients/{other_clinic_patient.id}/simulations", headers=AUTH_HEADER)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_send_simulation_email(
    client: AsyncClient, owner_user: User, completed_simulation: Simulation
):
    """POST /simulations/{id}/send-email should send email and return success."""
    with patch("app.services.email.send_share_email", return_value=True):
        resp = await client.post(
            f"/simulations/{completed_simulation.id}/send-email",
            headers=AUTH_HEADER,
            json={"email": "patient@example.com"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["to"] == "patient@example.com"
    assert "sent" in data["detail"].lower()


@pytest.mark.asyncio
async def test_send_simulation_email_uses_patient_email(
    client: AsyncClient, owner_user: User, completed_simulation: Simulation, patient: Patient
):
    """POST /simulations/{id}/send-email without email override should use patient's email."""
    with patch("app.services.email.send_share_email", return_value=True):
        resp = await client.post(
            f"/simulations/{completed_simulation.id}/send-email",
            headers=AUTH_HEADER,
            json={},
        )
    assert resp.status_code == 200
    assert resp.json()["to"] == "john@example.com"


@pytest.mark.asyncio
async def test_send_simulation_email_no_email_available(
    client: AsyncClient, owner_user: User, db_session: AsyncSession, clinic: Clinic
):
    """POST /simulations/{id}/send-email with no email should return 400."""
    # Create patient without email
    p = Patient(clinic_id=clinic.id, display_name="No Email")
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)

    s = Simulation(
        clinic_id=clinic.id,
        patient_id=p.id,
        created_by=owner_user.id,
        treatment_type="veneers",
        shade="natural",
        before_image_key=f"clinics/{clinic.id}/before/x.jpg",
        result_image_key=f"clinics/{clinic.id}/results/x.jpg",
        status="completed",
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)

    resp = await client.post(
        f"/simulations/{s.id}/send-email",
        headers=AUTH_HEADER,
        json={},
    )
    assert resp.status_code == 400
    assert "No email" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_send_simulation_email_failed_simulation(
    client: AsyncClient, owner_user: User, failed_simulation: Simulation
):
    """Cannot email a failed simulation."""
    resp = await client.post(
        f"/simulations/{failed_simulation.id}/send-email",
        headers=AUTH_HEADER,
        json={"email": "test@example.com"},
    )
    assert resp.status_code == 400
