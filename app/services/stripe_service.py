import logging
from datetime import datetime, timezone

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.clinic import Clinic

logger = logging.getLogger(__name__)


def _init_stripe() -> None:
    stripe.api_key = settings.stripe_secret_key


def create_checkout_session(clinic: Clinic, price_id: str) -> str:
    _init_stripe()

    if not clinic.stripe_customer_id:
        customer = stripe.Customer.create(
            metadata={"clinic_id": str(clinic.id)},
        )
        customer_id = customer.id
    else:
        customer_id = clinic.stripe_customer_id

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        allow_promotion_codes=True,
        success_url=f"{settings.frontend_url}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.frontend_url}/subscription/cancel",
        metadata={"clinic_id": str(clinic.id)},
    )

    return session.url, customer_id


def create_customer_portal_session(clinic: Clinic) -> str:
    _init_stripe()

    if not clinic.stripe_customer_id:
        raise ValueError("Clinic has no Stripe customer")

    session = stripe.billing_portal.Session.create(
        customer=clinic.stripe_customer_id,
        return_url=f"{settings.frontend_url}/settings",
    )

    return session.url


async def handle_webhook_event(
    payload: bytes,
    sig_header: str,
    db: AsyncSession,
) -> None:
    _init_stripe()

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.SignatureVerificationError:
        raise ValueError("Invalid webhook signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        clinic_id = data.get("metadata", {}).get("clinic_id")
        if not clinic_id:
            logger.warning("checkout.session.completed missing clinic_id in metadata")
            return

        result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
        clinic = result.scalar_one_or_none()
        if not clinic:
            logger.warning("checkout.session.completed: clinic %s not found", clinic_id)
            return

        clinic.stripe_customer_id = data.get("customer")
        clinic.stripe_subscription_id = data.get("subscription")
        clinic.subscription_status = "active"
        await db.flush()

    elif event_type == "customer.subscription.updated":
        sub_id = data.get("id")
        result = await db.execute(
            select(Clinic).where(Clinic.stripe_subscription_id == sub_id)
        )
        clinic = result.scalar_one_or_none()
        if not clinic:
            logger.warning("subscription.updated: no clinic for subscription %s", sub_id)
            return

        stripe_status = data.get("status")
        status_map = {
            "active": "active",
            "past_due": "past_due",
            "canceled": "canceled",
            "unpaid": "unpaid",
            "trialing": "trial",
        }
        clinic.subscription_status = status_map.get(stripe_status, stripe_status)

        period_end = data.get("current_period_end")
        if period_end:
            clinic.subscription_current_period_end = datetime.fromtimestamp(
                period_end, tz=timezone.utc
            )
        await db.flush()

    elif event_type == "customer.subscription.deleted":
        sub_id = data.get("id")
        result = await db.execute(
            select(Clinic).where(Clinic.stripe_subscription_id == sub_id)
        )
        clinic = result.scalar_one_or_none()
        if not clinic:
            return

        clinic.subscription_status = "canceled"
        await db.flush()

    elif event_type == "invoice.payment_failed":
        sub_id = data.get("subscription")
        if not sub_id:
            return
        result = await db.execute(
            select(Clinic).where(Clinic.stripe_subscription_id == sub_id)
        )
        clinic = result.scalar_one_or_none()
        if not clinic:
            return

        clinic.subscription_status = "past_due"
        await db.flush()

    else:
        logger.info("Unhandled Stripe event: %s", event_type)
