import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    clinic_name: str


class AcceptInviteRequest(BaseModel):
    invite_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    firebase_uid: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    user: UserResponse
    clinic: "ClinicResponse"


from app.schemas.clinic import ClinicResponse

MeResponse.model_rebuild()
