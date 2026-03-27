"""Tests for /subscription endpoints and subscription gating."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic import Clinic
from app.models.patient import Patient
from app.models.subscription import Subscription
from app.models.user import User
from tests.conftest import AUTH_HEADER


# ---------------------------------------------------------------------------
# Subscription status endpoint
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_subscription_status(client: AsyncClient, owner_user: User, clinic: Clinic):
    """GET /subscription/status should return the clinic's subscription info."""
    resp = await client.get("/subscription/status", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["subscription_status"] == "trial"
    assert data["plan"] == "trial"


# ---------------------------------------------------------------------------
# Checkout endpoint
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_checkout_monthly(client: AsyncClient, owner_user: User, clinic: Clinic):
    """POST /subscription/checkout with monthly plan should return a checkout URL."""
    with patch(
        "app.routers.subscription.create_checkout_session",
        return_value=("https://checkout.stripe.com/test", "cus_test123"),
    ):
        resp = await client.post(
            "/subscription/checkout",
            headers=AUTH_HEADER,
            json={"plan": "monthly"},
        )
    assert resp.status_code == 200
    assert resp.json()["checkout_url"] == "https://checkout.stripe.com/test"


@pytest.mark.asyncio
async def test_create_checkout_annual(client: AsyncClient, owner_user: User, clinic: Clinic):
    """POST /subscription/checkout with annual plan should work."""
    with patch(
        "app.routers.subscription.create_checkout_session",
        return_value=("https://checkout.stripe.com/annual", "cus_test123"),
    ):
        resp = await client.post(
            "/subscription/checkout",
            headers=AUTH_HEADER,
            json={"plan": "annual"},
        )
    assert resp.status_code == 200
    assert "checkout_url" in resp.json()


@pytest.mark.asyncio
async def test_create_checkout_invalid_plan(client: AsyncClient, owner_user: User, clinic: Clinic):
    """POST /subscription/checkout with invalid plan returns 400."""
    resp = await client.post(
        "/subscription/checkout",
        headers=AUTH_HEADER,
        json={"plan": "enterprise"},
    )
    assert resp.status_code == 400
    assert "Invalid plan" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_checkout_saves_customer_id(
    client: AsyncClient, owner_user: User, clinic: Clinic, db_session: AsyncSession
):
    """Checkout should save the Stripe customer ID on the clinic if it doesn't have one."""
    clinic_id = clinic.id  # capture before expire
    with patch(
        "app.routers.subscription.create_checkout_session",
        return_value=("https://checkout.stripe.com/test", "cus_new_customer"),
    ):
        resp = await client.post(
            "/subscription/checkout",
            headers=AUTH_HEADER,
            json={"plan": "monthly"},
        )
    assert resp.status_code == 200

    db_session.expire_all()
    result = await db_session.execute(select(Clinic).where(Clinic.id == clinic_id))
    refreshed = result.scalar_one()
    assert refreshed.stripe_customer_id == "cus_new_customer"


# ---------------------------------------------------------------------------
# Portal endpoint
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_portal_no_customer(client: AsyncClient, owner_user: User, clinic: Clinic):
    """POST /subscription/portal without a Stripe customer should return 400."""
    resp = await client.post("/subscription/portal", headers=AUTH_HEADER)
    assert resp.status_code == 400
    assert "No active subscription" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_portal_with_customer(
    client: AsyncClient, owner_user: User, db_session: AsyncSession, clinic: Clinic
):
    """POST /subscription/portal with a Stripe customer should return portal URL."""
    result = await db_session.execute(
        select(Subscription).where(Subscription.clinic_id == clinic.id)
    )
    sub = result.scalar_one()
    sub.stripe_customer_id = "cus_existing"
    await db_session.commit()

    with patch(
        "app.routers.subscription.create_customer_portal_session",
        return_value="https://billing.stripe.com/test",
    ):
        resp = await client.post("/subscription/portal", headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert resp.json()["portal_url"] == "https://billing.stripe.com/test"


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_webhook_no_signature_rejected(client: AsyncClient):
    """POST /subscription/webhook without stripe-signature header returns 400."""
    resp = await client.post("/subscription/webhook", content=b"payload")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected(client: AsyncClient):
    """POST /subscription/webhook with invalid signature returns 400."""
    import stripe as stripe_lib

    with patch(
        "app.services.stripe_service.stripe.Webhook.construct_event",
        side_effect=stripe_lib.SignatureVerificationError("Invalid signature", "sig_header"),
    ):
        resp = await client.post(
            "/subscription/webhook",
            content=b"payload",
            headers={"stripe-signature": "invalid"},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_checkout_completed(
    client: AsyncClient, db_session: AsyncSession, clinic: Clinic, owner_user: User
):
    """Webhook checkout.session.completed should activate the subscription."""
    clinic_id = clinic.id
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": "cus_webhook_test",
                "subscription": "sub_webhook_test",
                "metadata": {"clinic_id": str(clinic_id)},
            }
        },
    }

    with patch(
        "app.services.stripe_service.stripe.Webhook.construct_event",
        return_value=event,
    ):
        resp = await client.post(
            "/subscription/webhook",
            content=b"payload",
            headers={"stripe-signature": "valid"},
        )
    assert resp.status_code == 200

    db_session.expire_all()
    result = await db_session.execute(select(Clinic).where(Clinic.id == clinic_id))
    refreshed = result.scalar_one()
    assert refreshed.subscription_status == "active"
    assert refreshed.stripe_customer_id == "cus_webhook_test"
    assert refreshed.stripe_subscription_id == "sub_webhook_test"


@pytest.mark.asyncio
async def test_webhook_subscription_deleted(
    client: AsyncClient, db_session: AsyncSession, clinic: Clinic, owner_user: User
):
    """Webhook customer.subscription.deleted should cancel the subscription."""
    clinic_id = clinic.id
    # Set stripe_subscription_id on the Subscription record
    result = await db_session.execute(
        select(Subscription).where(Subscription.clinic_id == clinic_id)
    )
    sub = result.scalar_one()
    sub.stripe_subscription_id = "sub_cancel_test"
    sub.status = "active"
    await db_session.commit()

    event = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {"id": "sub_cancel_test"},
        },
    }

    with patch(
        "app.services.stripe_service.stripe.Webhook.construct_event",
        return_value=event,
    ):
        resp = await client.post(
            "/subscription/webhook",
            content=b"payload",
            headers={"stripe-signature": "valid"},
        )
    assert resp.status_code == 200

    db_session.expire_all()
    result = await db_session.execute(
        select(Subscription).where(Subscription.clinic_id == clinic_id)
    )
    refreshed_sub = result.scalar_one()
    assert refreshed_sub.status == "canceled"


@pytest.mark.asyncio
async def test_webhook_payment_failed(
    client: AsyncClient, db_session: AsyncSession, clinic: Clinic, owner_user: User
):
    """Webhook invoice.payment_failed should set status to past_due."""
    clinic_id = clinic.id
    # Set stripe_subscription_id on the Subscription record
    result = await db_session.execute(
        select(Subscription).where(Subscription.clinic_id == clinic_id)
    )
    sub = result.scalar_one()
    sub.stripe_subscription_id = "sub_fail_test"
    sub.status = "active"
    await db_session.commit()

    event = {
        "type": "invoice.payment_failed",
        "data": {
            "object": {"subscription": "sub_fail_test"},
        },
    }

    with patch(
        "app.services.stripe_service.stripe.Webhook.construct_event",
        return_value=event,
    ):
        resp = await client.post(
            "/subscription/webhook",
            content=b"payload",
            headers={"stripe-signature": "valid"},
        )
    assert resp.status_code == 200

    db_session.expire_all()
    result = await db_session.execute(
        select(Subscription).where(Subscription.clinic_id == clinic_id)
    )
    refreshed_sub = result.scalar_one()
    assert refreshed_sub.status == "past_due"


# ---------------------------------------------------------------------------
# Subscription gating tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_active_trial_allows_access(
    client: AsyncClient, db_session: AsyncSession, clinic: Clinic, owner_user: User
):
    """Clinics with active trial should access gated endpoints."""
    clinic.subscription_status = "trial"
    clinic.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db_session.commit()

    resp = await client.get("/patients", headers=AUTH_HEADER)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_expired_trial_blocks_access(
    client: AsyncClient, db_session: AsyncSession, clinic: Clinic, owner_user: User
):
    """Clinics with expired trial should be blocked from gated endpoints."""
    # Update the Subscription record (not the Clinic)
    result = await db_session.execute(
        select(Subscription).where(Subscription.clinic_id == clinic.id)
    )
    sub = result.scalar_one()
    sub.status = "trial"
    sub.trial_ends_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db_session.commit()

    resp = await client.get("/patients", headers=AUTH_HEADER)
    assert resp.status_code == 403
    assert "Trial has expired" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_active_subscription_allows_access(
    client: AsyncClient, db_session: AsyncSession, clinic: Clinic, owner_user: User
):
    """Clinics with active subscription should access gated endpoints."""
    result = await db_session.execute(
        select(Subscription).where(Subscription.clinic_id == clinic.id)
    )
    sub = result.scalar_one()
    sub.status = "active"
    sub.plan = "standard_monthly"
    await db_session.commit()

    resp = await client.get("/patients", headers=AUTH_HEADER)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_canceled_subscription_blocks_access(
    client: AsyncClient, db_session: AsyncSession, clinic: Clinic, owner_user: User
):
    """Clinics with canceled subscription should be blocked."""
    result = await db_session.execute(
        select(Subscription).where(Subscription.clinic_id == clinic.id)
    )
    sub = result.scalar_one()
    sub.status = "canceled"
    await db_session.commit()

    resp = await client.get("/patients", headers=AUTH_HEADER)
    assert resp.status_code == 403
    assert "Subscription required" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_past_due_blocks_access(
    client: AsyncClient, db_session: AsyncSession, clinic: Clinic, owner_user: User
):
    """Clinics with past_due payment should be blocked."""
    result = await db_session.execute(
        select(Subscription).where(Subscription.clinic_id == clinic.id)
    )
    sub = result.scalar_one()
    sub.status = "past_due"
    await db_session.commit()

    resp = await client.get("/patients", headers=AUTH_HEADER)
    assert resp.status_code == 403
    assert "past due" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ungated_endpoints_work_without_subscription(
    client: AsyncClient, db_session: AsyncSession, clinic: Clinic, owner_user: User
):
    """Auth, clinics, subscription, and health should work without subscription."""
    result = await db_session.execute(
        select(Subscription).where(Subscription.clinic_id == clinic.id)
    )
    sub = result.scalar_one()
    sub.status = "canceled"
    await db_session.commit()

    # /auth/me should work
    resp = await client.get("/auth/me", headers=AUTH_HEADER)
    assert resp.status_code == 200

    # /clinics/me should work
    resp = await client.get("/clinics/me", headers=AUTH_HEADER)
    assert resp.status_code == 200

    # /subscription/status should work
    resp = await client.get("/subscription/status", headers=AUTH_HEADER)
    assert resp.status_code == 200

    # /health should work
    resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_share_view_works_without_subscription(
    client: AsyncClient, share_token
):
    """Public share view should work regardless of subscription status."""
    resp = await client.get(f"/share/{share_token.token}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_registration_sets_trial(client: AsyncClient, db_session: AsyncSession):
    """POST /auth/register should create a clinic with trial status and trial_ends_at."""
    resp = await client.post(
        "/auth/register",
        headers=AUTH_HEADER,
        json={
            "email": "newtrial@example.com",
            "name": "Dr. Trial",
            "clinic_name": "Trial Dental",
        },
    )
    assert resp.status_code == 200
    clinic_id = resp.json()["clinic"]["id"]

    result = await db_session.execute(select(Clinic).where(Clinic.id == clinic_id))
    clinic = result.scalar_one()
    assert clinic.subscription_status == "trial"
    assert clinic.trial_ends_at is not None
    # Trial should be ~3 days from now
    delta = clinic.trial_ends_at - datetime.now(timezone.utc)
    assert 2 <= delta.days <= 3


@pytest.mark.asyncio
async def test_trial_daily_simulation_limit(
    client: AsyncClient, db_session: AsyncSession, clinic: Clinic, owner_user: User, patient: Patient
):
    """Trial accounts should be limited to 1 simulation per day."""
    # First simulation should succeed
    resp = await client.post(
        "/simulations",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(patient.id),
            "before_image_key": f"clinics/{clinic.id}/before/test.jpg",
            "treatment_type": "veneers",
            "shade": "natural",
        },
    )
    assert resp.status_code == 201

    # Second simulation on the same day should be blocked
    resp = await client.post(
        "/simulations",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(patient.id),
            "before_image_key": f"clinics/{clinic.id}/before/test2.jpg",
            "treatment_type": "whitening",
            "shade": "natural",
        },
    )
    assert resp.status_code == 429
    assert "Trial accounts are limited" in resp.json()["detail"]
    assert "Subscribe" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_active_subscription_no_daily_limit(
    client: AsyncClient, db_session: AsyncSession, clinic: Clinic, owner_user: User, patient: Patient
):
    """Active subscriptions should have no daily simulation limit."""
    result = await db_session.execute(
        select(Subscription).where(Subscription.clinic_id == clinic.id)
    )
    sub = result.scalar_one()
    sub.status = "active"
    sub.plan = "standard_monthly"
    await db_session.commit()

    for i in range(3):
        resp = await client.post(
            "/simulations",
            headers=AUTH_HEADER,
            json={
                "patient_id": str(patient.id),
                "before_image_key": f"clinics/{clinic.id}/before/test{i}.jpg",
                "treatment_type": "veneers",
                "shade": "natural",
            },
        )
        assert resp.status_code == 201
