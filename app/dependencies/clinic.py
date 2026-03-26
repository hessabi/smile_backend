from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.clinic import Clinic
from app.models.user import User


async def get_current_clinic(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Clinic:
    result = await db.execute(
        select(Clinic).where(Clinic.id == user.clinic_id)
    )
    clinic = result.scalar_one_or_none()

    if not clinic:
        raise HTTPException(status_code=403, detail="Clinic not found")

    if not clinic.is_active:
        raise HTTPException(status_code=403, detail="Clinic is deactivated")

    return clinic
