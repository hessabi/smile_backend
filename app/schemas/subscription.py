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
