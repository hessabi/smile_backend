import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.simulation import SimulationResponse


class AdminClinicResponse(BaseModel):
    id: uuid.UUID
    name: str
    plan: str
    subscription_status: str
    trial_ends_at: datetime | None
    subscription_current_period_end: datetime | None
    is_active: bool
    user_count: int = 0
    patient_count: int = 0
    simulation_count: int = 0
    created_at: datetime
    updated_at: datetime


class AdminClinicListResponse(BaseModel):
    clinics: list[AdminClinicResponse]
    total: int


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    clinic_name: str
    email: str
    name: str
    role: str
    is_active: bool
    is_platform_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminUserListResponse(BaseModel):
    users: list[AdminUserResponse]
    total: int


class AdminPatientResponse(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    clinic_name: str
    display_name: str
    external_id: str | None
    email: str | None
    phone: str | None
    created_at: datetime


class AdminPatientListResponse(BaseModel):
    patients: list[AdminPatientResponse]
    total: int


class AdminPatientDetailResponse(AdminPatientResponse):
    notes: str | None
    simulations: list[SimulationResponse] = []
