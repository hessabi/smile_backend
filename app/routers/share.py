import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.subscription import require_active_subscription
from app.models.clinic import Clinic
from app.models.share_token import ShareToken
from app.models.simulation import Simulation
from app.models.user import User
from app.schemas.share import PublicSimulationResponse, ShareResponse
from app.services.audit import log_action
from app.services.storage import generate_download_url

router = APIRouter(tags=["🔗 Share"])


@router.post("/simulations/{simulation_id}/share", response_model=ShareResponse, status_code=201, dependencies=[Depends(require_active_subscription)])
async def create_share_link(
    simulation_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Simulation).where(
            Simulation.id == simulation_id,
            Simulation.clinic_id == current_user.clinic_id,
        )
    )
    sim = result.scalar_one_or_none()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    if sim.status != "completed":
        raise HTTPException(status_code=400, detail="Can only share completed simulations")

    token_str = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.share_token_expiry_days)

    share_token = ShareToken(
        simulation_id=simulation_id,
        token=token_str,
        expires_at=expires_at,
        created_by=current_user.id,
    )
    db.add(share_token)
    await db.flush()

    share_url = f"{settings.share_base_url}/share/{token_str}"

    await log_action(
        db,
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="share.create",
        resource_type="share_token",
        resource_id=share_token.id,
        details={"simulation_id": str(simulation_id)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return ShareResponse(
        id=share_token.id,
        share_url=share_url,
        expires_at=expires_at,
    )


@router.get("/share/{token}", response_model=PublicSimulationResponse)
async def get_shared_simulation(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ShareToken).where(ShareToken.token == token)
    )
    share_token = result.scalar_one_or_none()

    if not share_token:
        raise HTTPException(status_code=404, detail="Share link not found")

    if share_token.revoked_at is not None:
        raise HTTPException(status_code=410, detail="Share link has been revoked")

    if share_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Share link has expired")

    result = await db.execute(
        select(Simulation).where(Simulation.id == share_token.simulation_id)
    )
    sim = result.scalar_one_or_none()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    result = await db.execute(
        select(Clinic).where(Clinic.id == sim.clinic_id)
    )
    clinic = result.scalar_one_or_none()

    result = await db.execute(
        select(User).where(User.id == sim.created_by)
    )
    provider = result.scalar_one_or_none()

    before_url = None
    preview_url = None
    try:
        before_url = generate_download_url(sim.before_image_key)
    except Exception:
        pass
    if sim.result_image_key:
        try:
            preview_url = generate_download_url(sim.result_image_key)
        except Exception:
            pass

    return PublicSimulationResponse(
        clinic_name=clinic.name if clinic else "Unknown Clinic",
        provider_name=provider.name if provider else "Unknown Provider",
        treatment_type=sim.treatment_type,
        shade=sim.shade,
        before_image_url=before_url,
        preview_image_url=preview_url,
        created_at=sim.created_at,
    )


@router.delete("/simulations/{simulation_id}/share/{token_id}", status_code=204)
async def revoke_share_link(
    simulation_id: uuid.UUID,
    token_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ShareToken).where(
            ShareToken.id == token_id,
            ShareToken.simulation_id == simulation_id,
        )
    )
    share_token = result.scalar_one_or_none()
    if not share_token:
        raise HTTPException(status_code=404, detail="Share token not found")

    sim_result = await db.execute(
        select(Simulation).where(
            Simulation.id == simulation_id,
            Simulation.clinic_id == current_user.clinic_id,
        )
    )
    if not sim_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Simulation not found")

    share_token.revoked_at = datetime.now(timezone.utc)
    await db.flush()

    await log_action(
        db,
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="share.revoke",
        resource_type="share_token",
        resource_id=token_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
