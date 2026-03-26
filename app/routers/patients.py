import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_verified_user
from app.dependencies.subscription import require_active_subscription
from app.models.patient import Patient
from app.models.user import User
from app.schemas.patient import PatientCreate, PatientListResponse, PatientResponse, PatientUpdate
from app.services.audit import log_action

router = APIRouter(prefix="/patients", tags=["👤 Patients"], dependencies=[Depends(require_active_subscription)])


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("", response_model=PatientListResponse)
async def list_patients(
    search: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(Patient).where(Patient.clinic_id == current_user.clinic_id)

    if search:
        escaped = _escape_like(search)
        search_filter = or_(
            Patient.display_name.ilike(f"%{escaped}%"),
            Patient.external_id.ilike(f"%{escaped}%"),
        )
        base = base.where(search_filter)

    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(
        base.order_by(Patient.created_at.desc()).limit(limit).offset(offset)
    )
    patients = result.scalars().all()

    return PatientListResponse(
        patients=[PatientResponse.model_validate(p) for p in patients],
        total=total,
    )


@router.post("", response_model=PatientResponse, status_code=201)
async def create_patient(
    body: PatientCreate,
    request: Request,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    patient = Patient(
        clinic_id=current_user.clinic_id,
        display_name=body.display_name,
        external_id=body.external_id,
        email=body.email,
        phone=body.phone,
        notes=body.notes,
    )
    db.add(patient)
    await db.flush()

    await log_action(
        db,
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="patient.create",
        resource_type="patient",
        resource_id=patient.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return PatientResponse.model_validate(patient)


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == current_user.clinic_id,
        )
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    return PatientResponse.model_validate(patient)


@router.put("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: uuid.UUID,
    body: PatientUpdate,
    request: Request,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == current_user.clinic_id,
        )
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if body.display_name is not None:
        patient.display_name = body.display_name
    if body.external_id is not None:
        patient.external_id = body.external_id
    if body.email is not None:
        patient.email = body.email
    if body.phone is not None:
        patient.phone = body.phone
    if body.notes is not None:
        patient.notes = body.notes

    await db.flush()

    await log_action(
        db,
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="patient.update",
        resource_type="patient",
        resource_id=patient.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    await db.refresh(patient)
    return PatientResponse.model_validate(patient)
