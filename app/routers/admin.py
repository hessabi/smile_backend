import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_platform_admin
from app.models.clinic import Clinic
from app.models.patient import Patient
from app.models.simulation import Simulation
from app.models.user import User
from app.schemas.admin import (
    AdminClinicListResponse,
    AdminClinicResponse,
    AdminPatientDetailResponse,
    AdminPatientListResponse,
    AdminPatientResponse,
    AdminUserListResponse,
    AdminUserResponse,
)
from app.schemas.simulation import SimulationResponse
from app.services.storage import generate_download_url

router = APIRouter(prefix="/admin", tags=["🔒 Platform Admin"])


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/clinics", response_model=AdminClinicListResponse)
async def list_all_clinics(
    search: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    base = select(Clinic)
    if search:
        base = base.where(Clinic.name.ilike(f"%{_escape_like(search)}%"))

    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(
        base.order_by(Clinic.created_at.desc()).limit(limit).offset(offset)
    )
    clinics = result.scalars().all()

    responses = []
    for c in clinics:
        user_count = (await db.execute(
            select(func.count()).where(User.clinic_id == c.id)
        )).scalar() or 0
        patient_count = (await db.execute(
            select(func.count()).where(Patient.clinic_id == c.id)
        )).scalar() or 0
        sim_count = (await db.execute(
            select(func.count()).where(Simulation.clinic_id == c.id)
        )).scalar() or 0

        responses.append(AdminClinicResponse(
            id=c.id,
            name=c.name,
            plan=c.plan,
            subscription_status=c.subscription_status,
            trial_ends_at=c.trial_ends_at,
            subscription_current_period_end=c.subscription_current_period_end,
            is_active=c.is_active,
            user_count=user_count,
            patient_count=patient_count,
            simulation_count=sim_count,
            created_at=c.created_at,
            updated_at=c.updated_at,
        ))

    return AdminClinicListResponse(clinics=responses, total=total)


@router.get("/clinics/{clinic_id}", response_model=AdminClinicResponse)
async def get_clinic_detail(
    clinic_id: uuid.UUID,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Clinic not found")

    user_count = (await db.execute(
        select(func.count()).where(User.clinic_id == c.id)
    )).scalar() or 0
    patient_count = (await db.execute(
        select(func.count()).where(Patient.clinic_id == c.id)
    )).scalar() or 0
    sim_count = (await db.execute(
        select(func.count()).where(Simulation.clinic_id == c.id)
    )).scalar() or 0

    return AdminClinicResponse(
        id=c.id,
        name=c.name,
        plan=c.plan,
        subscription_status=c.subscription_status,
        trial_ends_at=c.trial_ends_at,
        subscription_current_period_end=c.subscription_current_period_end,
        is_active=c.is_active,
        user_count=user_count,
        patient_count=patient_count,
        simulation_count=sim_count,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("/users", response_model=AdminUserListResponse)
async def list_all_users(
    search: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    base = select(User, Clinic.name.label("clinic_name")).join(Clinic, User.clinic_id == Clinic.id)
    if search:
        base = base.where(
            or_(User.name.ilike(f"%{_escape_like(search)}%"), User.email.ilike(f"%{_escape_like(search)}%"))
        )

    count_q = select(func.count()).select_from(select(User).subquery())
    if search:
        count_q = select(func.count()).select_from(
            select(User).where(
                or_(User.name.ilike(f"%{_escape_like(search)}%"), User.email.ilike(f"%{_escape_like(search)}%"))
            ).subquery()
        )
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(
        base.order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    rows = result.all()

    users = []
    for user, clinic_name in rows:
        users.append(AdminUserResponse(
            id=user.id,
            clinic_id=user.clinic_id,
            clinic_name=clinic_name,
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            is_platform_admin=user.is_platform_admin,
            created_at=user.created_at,
        ))

    return AdminUserListResponse(users=users, total=total)


@router.get("/patients", response_model=AdminPatientListResponse)
async def list_all_patients(
    search: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    base = select(Patient, Clinic.name.label("clinic_name")).join(
        Clinic, Patient.clinic_id == Clinic.id
    )
    if search:
        base = base.where(
            or_(
                Patient.display_name.ilike(f"%{_escape_like(search)}%"),
                Patient.external_id.ilike(f"%{_escape_like(search)}%"),
            )
        )

    count_q = select(func.count()).select_from(select(Patient).subquery())
    if search:
        count_q = select(func.count()).select_from(
            select(Patient).where(
                or_(
                    Patient.display_name.ilike(f"%{_escape_like(search)}%"),
                    Patient.external_id.ilike(f"%{_escape_like(search)}%"),
                )
            ).subquery()
        )
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(
        base.order_by(Patient.created_at.desc()).limit(limit).offset(offset)
    )
    rows = result.all()

    patients = []
    for patient, clinic_name in rows:
        patients.append(AdminPatientResponse(
            id=patient.id,
            clinic_id=patient.clinic_id,
            clinic_name=clinic_name,
            display_name=patient.display_name,
            external_id=patient.external_id,
            email=patient.email,
            phone=patient.phone,
            created_at=patient.created_at,
        ))

    return AdminPatientListResponse(patients=patients, total=total)


@router.get("/patients/{patient_id}", response_model=AdminPatientDetailResponse)
async def get_patient_detail(
    patient_id: uuid.UUID,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient, Clinic.name.label("clinic_name")).join(
            Clinic, Patient.clinic_id == Clinic.id
        ).where(Patient.id == patient_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Patient not found")

    patient, clinic_name = row

    sim_result = await db.execute(
        select(Simulation)
        .where(Simulation.patient_id == patient_id)
        .order_by(Simulation.created_at.desc())
    )
    sims = sim_result.scalars().all()

    sim_responses = []
    for sim in sims:
        resp = SimulationResponse.model_validate(sim)
        try:
            resp.before_image_url = generate_download_url(sim.before_image_key)
        except Exception:
            resp.before_image_url = None
        if sim.result_image_key:
            try:
                resp.result_image_url = generate_download_url(sim.result_image_key)
            except Exception:
                resp.result_image_url = None
        sim_responses.append(resp)

    return AdminPatientDetailResponse(
        id=patient.id,
        clinic_id=patient.clinic_id,
        clinic_name=clinic_name,
        display_name=patient.display_name,
        external_id=patient.external_id,
        email=patient.email,
        phone=patient.phone,
        notes=patient.notes,
        created_at=patient.created_at,
        simulations=sim_responses,
    )
