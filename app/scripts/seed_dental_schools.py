"""
Seed script for dental_schools table.

Usage:
    python -m app.scripts.seed_dental_schools
"""

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.database import async_session_factory, engine
from app.models.dental_school import DentalSchool


async def seed():
    data_path = Path(__file__).resolve().parent.parent / "data" / "dental_schools.json"
    with open(data_path) as f:
        schools = json.load(f)

    async with async_session_factory() as session:
        inserted = 0
        skipped = 0

        for school_data in schools:
            # Check if school with same name already exists
            result = await session.execute(
                select(DentalSchool).where(DentalSchool.name == school_data["name"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                skipped += 1
                continue

            school = DentalSchool(**school_data)
            session.add(school)
            inserted += 1

        await session.commit()
        print(f"Seed complete: {inserted} inserted, {skipped} skipped (already exist)")


if __name__ == "__main__":
    asyncio.run(seed())
