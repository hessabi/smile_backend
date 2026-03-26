from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.dental_school import DentalSchool
from app.schemas.dental_school import DentalSchoolResponse

router = APIRouter(prefix="/dental-schools", tags=["🎓 Dental Schools"])


@router.get("", response_model=list[DentalSchoolResponse])
async def list_dental_schools(
    search: str | None = Query(None, min_length=1, max_length=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(DentalSchool).where(DentalSchool.is_active.is_(True))

    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            DentalSchool.name.ilike(pattern)
            | DentalSchool.short_name.ilike(pattern)
            | DentalSchool.university.ilike(pattern)
        )

    stmt = stmt.order_by(DentalSchool.name)
    result = await db.execute(stmt)
    schools = result.scalars().all()
    return [DentalSchoolResponse.model_validate(s) for s in schools]
