"""
OpenAPI Documentation Components for SmilePreview API

This module aggregates detailed OpenAPI documentation from various component files
to provide comprehensive API documentation with examples, schemas, and detailed descriptions.
"""

from .admin_docs import get_admin_openapi_docs
from .audit_docs import get_audit_openapi_docs
from .auth_docs import get_auth_openapi_docs
from .clinics_docs import get_clinics_openapi_docs
from .consent_docs import get_consent_openapi_docs
from .health_docs import get_health_openapi_docs
from .images_docs import get_images_openapi_docs
from .patients_docs import get_patients_openapi_docs
from .post_procedure_docs import get_post_procedure_openapi_docs
from .share_docs import get_share_openapi_docs
from .simulations_docs import get_simulations_openapi_docs
from .subscription_docs import get_subscription_openapi_docs
from .team_docs import get_team_openapi_docs


def get_enhanced_openapi_docs():
    """
    Aggregate all OpenAPI documentation components into a single comprehensive schema.
    """
    docs = {}

    components = [
        get_auth_openapi_docs(),
        get_clinics_openapi_docs(),
        get_patients_openapi_docs(),
        get_simulations_openapi_docs(),
        get_images_openapi_docs(),
        get_consent_openapi_docs(),
        get_post_procedure_openapi_docs(),
        get_share_openapi_docs(),
        get_team_openapi_docs(),
        get_audit_openapi_docs(),
        get_subscription_openapi_docs(),
        get_admin_openapi_docs(),
        get_health_openapi_docs(),
    ]

    for component in components:
        for key, value in component.items():
            if key in docs:
                if isinstance(docs[key], dict) and isinstance(value, dict):
                    docs[key].update(value)
                elif isinstance(docs[key], list) and isinstance(value, list):
                    docs[key].extend(value)
            else:
                docs[key] = value

    return docs


def get_openapi_tags():
    """
    Define comprehensive tags for API organization.
    Organized in logical groups for better navigation.
    """
    return [
        # === CORE ===
        {
            "name": "🔐 Authentication",
            "description": "Clinic registration, Firebase JWT verification, and user session management",
        },
        {
            "name": "🏥 Clinics",
            "description": "Clinic profile management, settings, and configuration",
        },
        {
            "name": "👤 Patients",
            "description": "Patient records with search, creation, and updates scoped to your clinic",
        },

        # === SMILE SIMULATION ===
        {
            "name": "😁 Simulations",
            "description": "AI-powered smile preview generation, before/after comparison, PDF export, and email delivery",
        },
        {
            "name": "📸 Images",
            "description": "Secure GCS signed URL generation for uploading and downloading patient photos",
        },
        {
            "name": "🔗 Share",
            "description": "Public share links for patients to view their smile preview without logging in",
        },

        # === CLINICAL ===
        {
            "name": "📋 Post-Procedure",
            "description": "Post-procedure photo records linked to original simulations for comparison",
        },
        {
            "name": "✅ Consent",
            "description": "Patient consent tracking for service usage and training data opt-in",
        },

        # === BILLING ===
        {
            "name": "💳 Subscription",
            "description": "Stripe subscription management, checkout, customer portal, and webhook processing",
        },

        # === ADMIN ===
        {
            "name": "👥 Team",
            "description": "🔒 Owner/Admin Only - Invite staff, manage roles (provider, nurse, office_admin, owner)",
        },
        {
            "name": "📊 Audit",
            "description": "🔒 Owner/Admin Only - Append-only audit trail of all actions within the clinic",
        },
        {
            "name": "🔒 Platform Admin",
            "description": "🔒 Platform Admin Only - Cross-clinic visibility into all clinics, users, and patients",
        },

        # === SYSTEM ===
        {
            "name": "💚 Health",
            "description": "API health check and service status",
        },
    ]


def get_openapi_security_schemes():
    """
    Define security schemes for the API.
    """
    return {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "Firebase JWT",
            "description": (
                "Firebase ID token obtained from the client SDK. "
                "Include as: `Authorization: Bearer <firebase_id_token>`"
            ),
        },
    }


def get_common_responses():
    """
    Define common response schemas used across endpoints.
    """
    return {
        "ValidationError": {
            "description": "Validation Error",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "detail": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "loc": {"type": "array", "items": {"type": "string"}},
                                        "msg": {"type": "string"},
                                        "type": {"type": "string"},
                                    },
                                },
                            }
                        },
                    },
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "display_name"],
                                "msg": "field required",
                                "type": "value_error.missing",
                            }
                        ]
                    },
                }
            },
        },
        "Unauthorized": {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                    },
                    "example": {"detail": "Invalid or expired token"},
                }
            },
        },
        "Forbidden": {
            "description": "Insufficient permissions",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                    },
                    "example": {"detail": "Insufficient permissions"},
                }
            },
        },
        "NotFound": {
            "description": "Resource not found",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                    },
                    "example": {"detail": "Patient not found"},
                }
            },
        },
        "InternalServerError": {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                    },
                    "example": {"detail": "Internal server error"},
                }
            },
        },
    }
