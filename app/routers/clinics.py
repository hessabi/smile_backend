from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.clinic import get_current_clinic
from app.models.clinic import Clinic
from app.models.user import User
from app.schemas.clinic import ClinicResponse, ClinicUpdateRequest
from app.services.audit import log_action

router = APIRouter(prefix="/clinics", tags=["🏥 Clinics"])


@router.get("/me", response_model=ClinicResponse)
async def get_clinic(
    clinic: Clinic = Depends(get_current_clinic),
):
    return ClinicResponse.model_validate(clinic)


@router.put("/me", response_model=ClinicResponse)
async def update_clinic(
    body: ClinicUpdateRequest,
    request: Request,
    current_user: User = Depends(require_roles("owner", "office_admin")),
    clinic: Clinic = Depends(get_current_clinic),
    db: AsyncSession = Depends(get_db),
):
    if body.name is not None:
        clinic.name = body.name
    if body.settings is not None:
        clinic.settings = body.settings

    await db.flush()

    await log_action(
        db,
        clinic_id=clinic.id,
        user_id=current_user.id,
        action="clinic.update",
        resource_type="clinic",
        resource_id=clinic.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    await db.refresh(clinic)
    return ClinicResponse.model_validate(clinic)
