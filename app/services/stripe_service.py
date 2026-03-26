import logging
from datetime import datetime, timezone

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.clinic import Clinic
from app.models.subscription import Subscription

logger = logging.getLogger(__name__)


def _init_stripe() -> None:
    stripe.api_key = settings.stripe_secret_key


def create_checkout_session(subscription: Subscription, price_id: str) -> str:
    _init_stripe()

    if not subscription.stripe_customer_id:
        customer = stripe.Customer.create(
            metadata={"clinic_id": str(subscription.clinic_id)},
        )
        customer_id = customer.id
    else:
        customer_id = subscription.stripe_customer_id

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        allow_promotion_codes=True,
        success_url=f"{settings.frontend_url}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.frontend_url}/subscription/cancel",
        metadata={"clinic_id": str(subscription.clinic_id)},
    )

    return session.url, customer_id


def create_customer_portal_session(subscription: Subscription) -> str:
    _init_stripe()

    if not subscription.stripe_customer_id:
        raise ValueError("Subscription has no Stripe customer")

    session = stripe.billing_portal.Session.create(
        customer=subscription.stripe_customer_id,
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

        # Find subscription by clinic_id
        result = await db.execute(
            select(Subscription).where(Subscription.clinic_id == clinic_id)
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            logger.warning("checkout.session.completed: no subscription for clinic %s", clinic_id)
            return

        subscription.stripe_customer_id = data.get("customer")
        subscription.stripe_subscription_id = data.get("subscription")
        subscription.status = "active"
        subscription.plan = "standard_monthly"  # or determine from price
        await db.flush()

        # Also update clinic (deprecated, for backward compat)
        clinic_result = await db.execute(select(Clinic).where(Clinic.id == subscription.clinic_id))
        clinic = clinic_result.scalar_one_or_none()
        if clinic:
            clinic.stripe_customer_id = subscription.stripe_customer_id
            clinic.stripe_subscription_id = subscription.stripe_subscription_id
            clinic.subscription_status = subscription.status
            await db.flush()

    elif event_type == "customer.subscription.updated":
        sub_id = data.get("id")
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            logger.warning("subscription.updated: no subscription for stripe sub %s", sub_id)
            return

        stripe_status = data.get("status")
        status_map = {
            "active": "active",
            "past_due": "past_due",
            "canceled": "canceled",
            "unpaid": "unpaid",
            "trialing": "trial",
        }
        subscription.status = status_map.get(stripe_status, stripe_status)

        period_end = data.get("current_period_end")
        if period_end:
            subscription.current_period_end = datetime.fromtimestamp(
                period_end, tz=timezone.utc
            )
        await db.flush()

        # Also update clinic (deprecated, for backward compat)
        clinic_result = await db.execute(select(Clinic).where(Clinic.id == subscription.clinic_id))
        clinic = clinic_result.scalar_one_or_none()
        if clinic:
            clinic.subscription_status = subscription.status
            if period_end:
                clinic.subscription_current_period_end = subscription.current_period_end
            await db.flush()

    elif event_type == "customer.subscription.deleted":
        sub_id = data.get("id")
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            return

        subscription.status = "canceled"
        await db.flush()

        # Also update clinic (deprecated, for backward compat)
        clinic_result = await db.execute(select(Clinic).where(Clinic.id == subscription.clinic_id))
        clinic = clinic_result.scalar_one_or_none()
        if clinic:
            clinic.subscription_status = "canceled"
            await db.flush()

    elif event_type == "invoice.payment_failed":
        sub_id = data.get("subscription")
        if not sub_id:
            return
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            return

        subscription.status = "past_due"
        await db.flush()

        # Also update clinic (deprecated, for backward compat)
        clinic_result = await db.execute(select(Clinic).where(Clinic.id == subscription.clinic_id))
        clinic = clinic_result.scalar_one_or_none()
        if clinic:
            clinic.subscription_status = "past_due"
            await db.flush()

    else:
        logger.info("Unhandled Stripe event: %s", event_type)


def create_student_stripe_subscription(clinic_id: str, email: str) -> tuple[str, str]:
    """Creates a $0 Stripe subscription for a student. Returns (customer_id, subscription_id)."""
    _init_stripe()

    customer = stripe.Customer.create(
        email=email,
        metadata={"clinic_id": clinic_id, "plan": "student"},
    )

    subscription = stripe.Subscription.create(
        customer=customer.id,
        items=[{"price": settings.stripe_price_id_student}],
        metadata={"clinic_id": clinic_id, "plan": "student"},
    )

    return customer.id, subscription.id
