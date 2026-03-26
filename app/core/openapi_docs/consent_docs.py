"""
Consent endpoints OpenAPI documentation
"""


def get_consent_openapi_docs():
    return {
        "paths": {
            "/consent": {
                "post": {
                    "tags": ["✅ Consent"],
                    "summary": "Record Patient Consent",
                    "description": """
**Record a patient's consent decision**

Tracks whether a patient has granted consent for service usage or training data.
Each consent record is timestamped and linked to the staff member who recorded it.

**Consent Types:**
- `service_usage` - Consent to use SmilePreview for their dental consultation
- `training_data` - Consent to use anonymized images for AI model improvement

**Note:** Consent records are append-only. To revoke consent, create a new record
with `granted: false`. The `granted_by` field should contain the patient's name
as confirmation of who provided verbal or written consent.
                    """,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "example": {
                                    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                                    "consent_type": "service_usage",
                                    "granted": True,
                                    "granted_by": "John Doe",
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {"description": "Consent recorded"},
                        "400": {"description": "Invalid consent type"},
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                }
            },
            "/patients/{patient_id}/consent": {
                "get": {
                    "tags": ["✅ Consent"],
                    "summary": "Get Patient Consent Records",
                    "description": "**List all consent records for a patient**, ordered by most recent first.",
                    "responses": {
                        "200": {"description": "List of consent records"},
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                }
            },
        }
    }
