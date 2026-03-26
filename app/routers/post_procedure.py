import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.subscription import require_active_subscription
from app.models.patient import Patient
from app.models.post_procedure import PostProcedureImage
from app.models.user import User
from app.schemas.post_procedure import PostProcedureCreate, PostProcedureResponse
from app.services.audit import log_action
from app.services.storage import generate_download_url

router = APIRouter(tags=["📋 Post-Procedure"], dependencies=[Depends(require_active_subscription)])


@router.post(
    "/patients/{patient_id}/post-procedure",
    response_model=PostProcedureResponse,
    status_code=201,
)
async def create_post_procedure(
    patient_id: uuid.UUID,
    body: PostProcedureCreate,
    request: Request,
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

    clinic_prefix = f"clinics/{current_user.clinic_id}/"
    if not body.image_key.startswith(clinic_prefix):
        raise HTTPException(status_code=403, detail="Invalid image key")

    record = PostProcedureImage(
        clinic_id=current_user.clinic_id,
        patient_id=patient_id,
        simulation_id=body.simulation_id,
        uploaded_by=current_user.id,
        image_key=body.image_key,
        procedure_date=body.procedure_date,
        notes=body.notes,
    )
    db.add(record)
    await db.flush()

    await log_action(
        db,
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="post_procedure.create",
        resource_type="post_procedure",
        resource_id=record.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    resp = PostProcedureResponse.model_validate(record)
    try:
        resp.image_url = generate_download_url(record.image_key)
    except Exception:
        resp.image_url = None
    return resp


@router.get(
    "/patients/{patient_id}/post-procedure",
    response_model=list[PostProcedureResponse],
)
async def list_post_procedure(
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
        select(PostProcedureImage)
        .where(
            PostProcedureImage.patient_id == patient_id,
            PostProcedureImage.clinic_id == current_user.clinic_id,
        )
        .order_by(PostProcedureImage.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    responses = []
    for record in result.scalars().all():
        resp = PostProcedureResponse.model_validate(record)
        try:
            resp.image_url = generate_download_url(record.image_key)
        except Exception:
            resp.image_url = None
        responses.append(resp)
    return responses
