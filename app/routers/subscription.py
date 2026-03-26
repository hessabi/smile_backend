import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request

logger = logging.getLogger(__name__)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.clinic import Clinic
from app.models.user import User
from app.schemas.subscription import (
    CheckoutRequest,
    CheckoutResponse,
    PortalResponse,
    SubscriptionStatusResponse,
)
from app.services.audit import log_action
from app.services.stripe_service import (
    create_checkout_session,
    create_customer_portal_session,
    handle_webhook_event,
)

router = APIRouter(prefix="/subscription", tags=["💳 Subscription"])


@router.get("/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Clinic).where(Clinic.id == current_user.clinic_id))
    clinic = result.scalar_one_or_none()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")

    return SubscriptionStatusResponse(
        subscription_status=clinic.subscription_status,
        plan=clinic.plan,
        trial_ends_at=clinic.trial_ends_at,
        current_period_end=clinic.subscription_current_period_end,
        stripe_customer_id=clinic.stripe_customer_id,
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.plan == "monthly":
        price_id = settings.stripe_price_id_monthly
    elif body.plan == "annual":
        price_id = settings.stripe_price_id_annual
    else:
        raise HTTPException(status_code=400, detail="Invalid plan. Must be 'monthly' or 'annual'.")

    if not price_id:
        raise HTTPException(status_code=500, detail="Stripe price not configured")

    result = await db.execute(select(Clinic).where(Clinic.id == current_user.clinic_id))
    clinic = result.scalar_one_or_none()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")

    try:
        checkout_url, customer_id = create_checkout_session(clinic, price_id)
    except Exception:
        logger.exception("Stripe checkout session creation failed")
        raise HTTPException(status_code=500, detail="Failed to create checkout session. Please try again.")

    if not clinic.stripe_customer_id:
        clinic.stripe_customer_id = customer_id
        await db.flush()

    await log_action(
        db,
        clinic_id=clinic.id,
        user_id=current_user.id,
        action="subscription.checkout_created",
        resource_type="subscription",
        details={"plan": body.plan},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return CheckoutResponse(checkout_url=checkout_url)


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Clinic).where(Clinic.id == current_user.clinic_id))
    clinic = result.scalar_one_or_none()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")

    if not clinic.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No active subscription. Please subscribe first.")

    try:
        portal_url = create_customer_portal_session(clinic)
    except Exception:
        logger.exception("Stripe portal session creation failed")
        raise HTTPException(status_code=500, detail="Failed to create portal session. Please try again.")

    return PortalResponse(portal_url=portal_url)


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str = Header(None, alias="stripe-signature"),
):
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    payload = await request.body()

    try:
        await handle_webhook_event(payload, stripe_signature, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "ok"}
