import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.auth import require_roles
from app.dependencies.subscription import require_active_subscription
from app.models.clinic import Clinic
from app.models.user import User
from app.schemas.team import ALLOWED_ROLES, InviteRequest, TeamMemberResponse, TeamUpdateRequest
from app.services.audit import log_action

router = APIRouter(prefix="/team", tags=["👥 Team"], dependencies=[Depends(require_active_subscription)])


@router.get("", response_model=list[TeamMemberResponse])
async def list_team(
    current_user: User = Depends(require_roles("owner", "office_admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .where(User.clinic_id == current_user.clinic_id)
        .order_by(User.created_at)
    )
    return [TeamMemberResponse.model_validate(u) for u in result.scalars().all()]


@router.post("/invite", response_model=TeamMemberResponse, status_code=201)
async def invite_team_member(
    body: InviteRequest,
    request: Request,
    current_user: User = Depends(require_roles("owner", "office_admin")),
    db: AsyncSession = Depends(get_db),
):
    # Check if clinic is a student account
    clinic_result = await db.execute(select(Clinic).where(Clinic.id == current_user.clinic_id))
    clinic = clinic_result.scalar_one_or_none()
    if clinic and clinic.account_type == "student":
        raise HTTPException(status_code=403, detail="Student accounts are limited to 1 user")

    if body.role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {', '.join(ALLOWED_ROLES)}",
        )

    if body.role == "owner" and current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Only owners can create other owners")

    # Enforce seat limit
    count_result = await db.execute(
        select(func.count()).where(User.clinic_id == current_user.clinic_id)
    )
    user_count = count_result.scalar() or 0
    if user_count >= settings.max_clinic_users:
        raise HTTPException(
            status_code=403,
            detail=f"User limit reached. Maximum {settings.max_clinic_users} users per clinic.",
        )

    result = await db.execute(
        select(User).where(User.email == body.email, User.clinic_id == current_user.clinic_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="A user with this email already exists in your clinic")

    invite_token = str(uuid.uuid4())
    user = User(
        clinic_id=current_user.clinic_id,
        firebase_uid=f"pending_{uuid.uuid4().hex[:16]}",
        email=body.email,
        name=body.name,
        role=body.role,
        is_active=True,
        invite_token=invite_token,
    )
    db.add(user)
    await db.flush()

    await log_action(
        db,
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="team.invite",
        resource_type="user",
        resource_id=user.id,
        details={"email": body.email, "role": body.role},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return TeamMemberResponse.model_validate(user)


@router.put("/{user_id}", response_model=TeamMemberResponse)
async def update_team_member(
    user_id: uuid.UUID,
    body: TeamUpdateRequest,
    request: Request,
    current_user: User = Depends(require_roles("owner", "office_admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.clinic_id == current_user.clinic_id,
        )
    )
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if target_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot modify your own account via this endpoint")

    if body.role is not None:
        if body.role not in ALLOWED_ROLES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role. Must be one of: {', '.join(ALLOWED_ROLES)}",
            )
        if body.role == "owner" and current_user.role != "owner":
            raise HTTPException(status_code=403, detail="Only owners can assign the owner role")
        target_user.role = body.role

    if body.is_active is not None:
        target_user.is_active = body.is_active

    await db.flush()

    await log_action(
        db,
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="team.update",
        resource_type="user",
        resource_id=target_user.id,
        details={"changes": body.model_dump(exclude_none=True)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    await db.refresh(target_user)
    return TeamMemberResponse.model_validate(target_user)
