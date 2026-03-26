import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, model_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    clinic_name: str
    account_type: str = "practice"  # "practice" or "student"
    dental_school_id: uuid.UUID | None = None
    expected_graduation_date: date | None = None

    @model_validator(mode="after")
    def validate_student_fields(self):
        if self.account_type == "student":
            if not self.dental_school_id:
                raise ValueError("dental_school_id is required for student accounts")
            if not self.expected_graduation_date:
                raise ValueError("expected_graduation_date is required for student accounts")
        return self


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
    email_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    user: UserResponse
    clinic: "ClinicResponse"
    subscription: "SubscriptionResponse | None" = None


from app.schemas.clinic import ClinicResponse
from app.schemas.subscription import SubscriptionResponse

MeResponse.model_rebuild()
