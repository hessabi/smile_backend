from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.clinic import Clinic
from app.models.user import User


async def require_active_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(
        select(Clinic).where(Clinic.id == current_user.clinic_id)
    )
    clinic = result.scalar_one_or_none()
    if not clinic:
        raise HTTPException(status_code=403, detail="Clinic not found")

    status = clinic.subscription_status

    if status == "active":
        return current_user

    if status == "trial":
        if clinic.trial_ends_at and clinic.trial_ends_at > datetime.now(timezone.utc):
            return current_user
        raise HTTPException(
            status_code=403,
            detail="Trial has expired. Please subscribe to continue.",
        )

    if status == "past_due":
        raise HTTPException(
            status_code=403,
            detail="Payment past due. Please update your payment method.",
        )

    raise HTTPException(
        status_code=403,
        detail="Subscription required. Please subscribe to continue.",
    )
