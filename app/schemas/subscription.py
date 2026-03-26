import uuid
from datetime import datetime

from pydantic import BaseModel


class CheckoutRequest(BaseModel):
    plan: str


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


class SubscriptionStatusResponse(BaseModel):
    subscription_status: str
    plan: str
    trial_ends_at: datetime | None
    current_period_end: datetime | None
    stripe_customer_id: str | None


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    plan: str
    status: str
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    stripe_price_id: str | None = None
    trial_ends_at: datetime | None = None
    current_period_end: datetime | None = None
    seat_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
