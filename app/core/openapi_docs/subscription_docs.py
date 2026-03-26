"""
Subscription endpoints OpenAPI documentation
"""


def get_subscription_openapi_docs():
    return {
        "paths": {
            "/subscription/status": {
                "get": {
                    "tags": ["💳 Subscription"],
                    "summary": "Get Subscription Status",
                    "description": """
**Get the current clinic's subscription status**

Returns the subscription status, plan type, trial expiry, and current billing period end.
Used by the frontend to determine what UI to show (trial banner, upgrade prompt, etc.).

**Statuses:** `trial`, `active`, `past_due`, `canceled`, `unpaid`
                    """,
                    "responses": {
                        "200": {
                            "description": "Subscription status",
                            "content": {
                                "application/json": {
                                    "example": {
                                        "subscription_status": "trial",
                                        "plan": "trial",
                                        "trial_ends_at": "2026-04-07T10:00:00Z",
                                        "current_period_end": None,
                                        "stripe_customer_id": None,
                                    }
                                }
                            },
                        },
                    },
                }
            },
            "/subscription/checkout": {
                "post": {
                    "tags": ["💳 Subscription"],
                    "summary": "Create Checkout Session",
                    "description": """
**Create a Stripe Checkout Session and return the redirect URL**

The frontend redirects the user to the Stripe-hosted checkout page.
Stripe handles all payment collection. On success, Stripe redirects
back to your `success_url` and fires a webhook to update the subscription status.

**Plans:** `monthly` or `annual`

Creates a Stripe Customer if the clinic doesn't have one yet.
                    """,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "example": {"plan": "monthly"},
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Checkout URL",
                            "content": {
                                "application/json": {
                                    "example": {
                                        "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_...",
                                    }
                                }
                            },
                        },
                        "400": {"description": "Invalid plan"},
                    },
                }
            },
            "/subscription/portal": {
                "post": {
                    "tags": ["💳 Subscription"],
                    "summary": "Create Customer Portal Session",
                    "description": """
**Create a Stripe Customer Portal session for self-service subscription management**

The portal lets customers update payment methods, change plans, view invoices,
and cancel their subscription. Stripe hosts the entire experience.

**Requires:** An existing Stripe customer (must have gone through checkout at least once).
                    """,
                    "responses": {
                        "200": {
                            "description": "Portal URL",
                            "content": {
                                "application/json": {
                                    "example": {
                                        "portal_url": "https://billing.stripe.com/p/session/...",
                                    }
                                }
                            },
                        },
                        "400": {"description": "No Stripe customer exists"},
                    },
                }
            },
        }
    }
