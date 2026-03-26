import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.subscription import require_active_subscription
from app.models.consent import ConsentRecord
from app.models.patient import Patient
from app.models.user import User
from app.schemas.consent import ConsentCreate, ConsentResponse
from app.services.audit import log_action

router = APIRouter(tags=["✅ Consent"], dependencies=[Depends(require_active_subscription)])


@router.post("/consent", response_model=ConsentResponse, status_code=201)
async def record_consent(
    body: ConsentCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(
            Patient.id == body.patient_id,
            Patient.clinic_id == current_user.clinic_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Patient not found")

    if body.consent_type not in ("service_usage", "training_data"):
        raise HTTPException(status_code=400, detail="Invalid consent type")

    record = ConsentRecord(
        clinic_id=current_user.clinic_id,
        patient_id=body.patient_id,
        consent_type=body.consent_type,
        granted=body.granted,
        granted_by=body.granted_by,
        recorded_by=current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(record)
    await db.flush()

    await log_action(
        db,
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="consent.record",
        resource_type="consent",
        resource_id=record.id,
        details={"consent_type": body.consent_type, "granted": body.granted},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return ConsentResponse.model_validate(record)


@router.get("/patients/{patient_id}/consent", response_model=list[ConsentResponse])
async def get_patient_consent(
    patient_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == current_user.clinic_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Patient not found")

    result = await db.execute(
        select(ConsentRecord)
        .where(
            ConsentRecord.patient_id == patient_id,
            ConsentRecord.clinic_id == current_user.clinic_id,
        )
        .order_by(ConsentRecord.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    return [ConsentResponse.model_validate(r) for r in result.scalars().all()]
