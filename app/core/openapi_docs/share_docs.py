"""
Share endpoints OpenAPI documentation
"""


def get_share_openapi_docs():
    return {
        "paths": {
            "/share/{token}": {
                "get": {
                    "tags": ["🔗 Share"],
                    "summary": "View Shared Simulation (Public)",
                    "description": """
**Public endpoint - no authentication required**

Retrieves a shared smile preview using the unique share token.
Returns clinic name, provider name, treatment details, and signed image URLs.

**Security:**
- Token is validated for existence and expiration
- Returns 410 Gone if the link has expired
- Image URLs are freshly signed (15-minute expiry) on each request

**Used by:** The public-facing share page on the frontend, typically linked
from the patient email.

**Response includes a disclaimer** that this is an AI-generated simulation.
                    """,
                    "responses": {
                        "200": {
                            "description": "Public simulation view",
                            "content": {
                                "application/json": {
                                    "example": {
                                        "clinic_name": "Smith Family Dental",
                                        "provider_name": "Dr. Sarah Smith",
                                        "treatment_type": "veneers",
                                        "shade": "natural",
                                        "before_image_url": "https://storage.googleapis.com/...",
                                        "preview_image_url": "https://storage.googleapis.com/...",
                                        "created_at": "2026-03-24T10:05:00Z",
                                        "disclaimer": "This is an AI-generated simulation for illustration purposes only...",
                                    }
                                }
                            },
                        },
                        "404": {
                            "description": "Share token not found",
                            "content": {
                                "application/json": {
                                    "example": {"detail": "Share link not found"},
                                }
                            },
                        },
                        "410": {
                            "description": "Share link expired",
                            "content": {
                                "application/json": {
                                    "example": {"detail": "Share link has expired"},
                                }
                            },
                        },
                    },
                }
            },
        }
    }
