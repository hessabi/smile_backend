import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


ALLOWED_ROLES = ("provider", "nurse", "office_admin", "owner")


class TeamMemberResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: str
    is_active: bool
    invite_token: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InviteRequest(BaseModel):
    email: EmailStr
    name: str
    role: str


class TeamUpdateRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None
