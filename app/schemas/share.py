import uuid
from datetime import datetime

from pydantic import BaseModel


class ShareResponse(BaseModel):
    id: uuid.UUID
    share_url: str
    expires_at: datetime


class PublicSimulationResponse(BaseModel):
    clinic_name: str
    provider_name: str
    treatment_type: str
    shade: str
    before_image_url: str | None
    preview_image_url: str | None
    created_at: datetime
    disclaimer: str = (
        "This is an AI-generated simulation for illustration purposes only. "
        "Actual results may vary. Consult your dental professional for personalized treatment plans."
    )
