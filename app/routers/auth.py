from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from firebase_admin import auth as firebase_auth
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.clinic import Clinic
from app.models.user import User
from app.schemas.auth import AcceptInviteRequest, MeResponse, RegisterRequest, UserResponse
from app.schemas.clinic import ClinicResponse
from app.services.audit import log_action

router = APIRouter(prefix="/auth", tags=["🔐 Authentication"])


@router.post("/register", response_model=MeResponse)
async def register(
    body: RegisterRequest,
    request: Request,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    # C1 fix: Extract UID from verified token, not from request body
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]
    try:
        decoded = firebase_auth.verify_id_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    firebase_uid = decoded.get("uid")
    if not firebase_uid:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    result = await db.execute(
        select(User).where(User.firebase_uid == firebase_uid)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already registered")

    clinic = Clinic(
        name=body.clinic_name,
        subscription_status="trial",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=settings.trial_days),
    )
    db.add(clinic)
    await db.flush()

    user = User(
        clinic_id=clinic.id,
        firebase_uid=firebase_uid,
        email=body.email,
        name=body.name,
        role="owner",
    )
    db.add(user)
    await db.flush()

    await log_action(
        db,
        clinic_id=clinic.id,
        user_id=user.id,
        action="user.register",
        resource_type="user",
        resource_id=user.id,
        details={"email": body.email, "clinic_name": body.clinic_name},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return MeResponse(
        user=UserResponse.model_validate(user),
        clinic=ClinicResponse.model_validate(clinic),
    )


@router.post("/accept-invite", response_model=MeResponse)
async def accept_invite(
    body: AcceptInviteRequest,
    request: Request,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]
    try:
        decoded = firebase_auth.verify_id_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    firebase_uid = decoded.get("uid")
    firebase_email = decoded.get("email", "")
    if not firebase_uid:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Look up pending user by invite token
    result = await db.execute(
        select(User).where(User.invite_token == body.invite_token)
    )
    pending_user = result.scalar_one_or_none()
    if not pending_user:
        raise HTTPException(status_code=404, detail="Invalid invite token")

    if not pending_user.firebase_uid.startswith("pending_"):
        raise HTTPException(status_code=400, detail="Invite already accepted")

    if pending_user.email.lower() != firebase_email.lower():
        raise HTTPException(status_code=400, detail="Email does not match invite")

    # Activate the pending user
    pending_user.firebase_uid = firebase_uid
    pending_user.invite_accepted_at = datetime.now(timezone.utc)
    await db.flush()

    # Get clinic
    clinic_result = await db.execute(
        select(Clinic).where(Clinic.id == pending_user.clinic_id)
    )
    clinic = clinic_result.scalar_one_or_none()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")

    await log_action(
        db,
        clinic_id=clinic.id,
        user_id=pending_user.id,
        action="user.accept_invite",
        resource_type="user",
        resource_id=pending_user.id,
        details={"email": pending_user.email},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return MeResponse(
        user=UserResponse.model_validate(pending_user),
        clinic=ClinicResponse.model_validate(clinic),
    )


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Clinic).where(Clinic.id == current_user.clinic_id)
    )
    clinic = result.scalar_one_or_none()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")

    return MeResponse(
        user=UserResponse.model_validate(current_user),
        clinic=ClinicResponse.model_validate(clinic),
    )
