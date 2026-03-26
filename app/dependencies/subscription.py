from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.subscription import Subscription
from app.models.user import User


async def require_active_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Find subscription for this user's clinic
    result = await db.execute(
        select(Subscription).where(Subscription.clinic_id == current_user.clinic_id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=403, detail="Subscription required. Please subscribe to continue.")

    status = subscription.status

    if status == "active":
        # Check student expiration
        if subscription.plan == "student" and subscription.current_period_end:
            if subscription.current_period_end < datetime.now(timezone.utc):
                raise HTTPException(status_code=403, detail="Student access has expired. Contact support to upgrade.")
        return current_user

    if status == "trial":
        if subscription.trial_ends_at and subscription.trial_ends_at > datetime.now(timezone.utc):
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
