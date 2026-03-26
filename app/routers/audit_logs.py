from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, BeforeValidator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_roles
from app.models.audit import AuditLog
from app.models.user import User

router = APIRouter(prefix="/audit-logs", tags=["📊 Audit"])

InetStr = Annotated[str | None, BeforeValidator(lambda v: str(v) if v is not None else None)]


class AuditLogEntry(BaseModel):
    id: int
    clinic_id: UUID
    user_id: UUID | None
    action: str
    resource_type: str | None
    resource_id: UUID | None
    details: dict | None
    ip_address: InetStr = None
    user_agent: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogEntry]
    total: int


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_roles("owner", "office_admin")),
    db: AsyncSession = Depends(get_db),
):
    base = select(AuditLog).where(AuditLog.clinic_id == current_user.clinic_id)

    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(
        base.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    )
    logs = result.scalars().all()

    return AuditLogListResponse(
        logs=[AuditLogEntry.model_validate(log) for log in logs],
        total=total,
    )
