"""
Clinic endpoints OpenAPI documentation
"""


def get_clinics_openapi_docs():
    return {
        "paths": {
            "/clinics/me": {
                "get": {
                    "tags": ["🏥 Clinics"],
                    "summary": "Get My Clinic",
                    "description": """
**Retrieve the current user's clinic profile**

Returns clinic name, plan, settings, and status.
The clinic ID is derived from the authenticated user's record -- never passed as a parameter.
                    """,
                    "responses": {
                        "200": {"description": "Clinic details"},
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                        "403": {"$ref": "#/components/responses/Forbidden"},
                    },
                },
                "put": {
                    "tags": ["🏥 Clinics"],
                    "summary": "Update My Clinic",
                    "description": """
**Update clinic name or settings**

Partial updates supported -- only include fields you want to change.

**Settings** is a freeform JSON object for clinic-specific configuration
(e.g., default treatment types, branding preferences).
                    """,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string", "example": "Smith Family Dental"},
                                        "settings": {
                                            "type": "object",
                                            "example": {"default_shade": "natural", "branding_color": "#2563eb"},
                                        },
                                    },
                                },
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Updated clinic"},
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                    },
                },
            }
        }
    }
