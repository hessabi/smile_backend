import uuid
from datetime import datetime

from pydantic import BaseModel


class SimulationCreate(BaseModel):
    patient_id: uuid.UUID
    before_image_key: str
    treatment_type: str
    shade: str


class SimulationResponse(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    patient_id: uuid.UUID
    created_by: uuid.UUID
    treatment_type: str
    shade: str
    prompt_used: str | None
    model_version: str | None
    before_image_key: str
    result_image_key: str | None
    status: str
    error_message: str | None
    generation_time_ms: int | None
    created_at: datetime
    before_image_url: str | None = None
    result_image_url: str | None = None

    model_config = {"from_attributes": True}


class FullSimulationResponse(SimulationResponse):
    post_procedure_image_url: str | None = None


class SendEmailRequest(BaseModel):
    email: str | None = None
