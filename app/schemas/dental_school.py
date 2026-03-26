import uuid

from pydantic import BaseModel


class DentalSchoolResponse(BaseModel):
    id: uuid.UUID
    name: str
    short_name: str | None
    university: str | None
    city: str
    state: str
    country: str
    email_domain: str | None

    model_config = {"from_attributes": True}
