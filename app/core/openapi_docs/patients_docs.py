"""
Patient endpoints OpenAPI documentation
"""


def get_patients_openapi_docs():
    return {
        "paths": {
            "/patients": {
                "get": {
                    "tags": ["👤 Patients"],
                    "summary": "List Patients",
                    "description": """
**List patients for the current clinic with search and pagination**

Search matches against `display_name` and `external_id` (case-insensitive partial match).
Results are ordered by most recently created.

**Query Parameters:**
- `search` - Filter by name or external ID
- `limit` - Results per page (1-100, default 20)
- `offset` - Pagination offset (default 0)

**Security:** Only returns patients belonging to the authenticated user's clinic.
                    """,
                    "responses": {
                        "200": {
                            "description": "Paginated patient list",
                            "content": {
                                "application/json": {
                                    "example": {
                                        "patients": [
                                            {
                                                "id": "550e8400-e29b-41d4-a716-446655440000",
                                                "clinic_id": "660e8400-e29b-41d4-a716-446655440000",
                                                "display_name": "John D.",
                                                "external_id": "PAT-001",
                                                "email": "john@example.com",
                                                "phone": "+15125551234",
                                                "notes": None,
                                                "created_at": "2026-03-24T10:00:00Z",
                                                "updated_at": "2026-03-24T10:00:00Z",
                                            }
                                        ],
                                        "total": 1,
                                    }
                                }
                            },
                        },
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                    },
                },
                "post": {
                    "tags": ["👤 Patients"],
                    "summary": "Create Patient",
                    "description": """
**Create a new patient record**

Patients are scoped to the current clinic. The `external_id` field can be used
to link with your practice management system (e.g., Dentrix, Open Dental).

**Fields:**
- `display_name` (required) - Patient's display name (can use initials for privacy)
- `external_id` (optional) - ID from your practice management system
- `email` (optional) - Patient email for sending smile previews
- `phone` (optional) - Patient phone number
- `notes` (optional) - Internal notes
                    """,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "example": {
                                    "display_name": "John D.",
                                    "external_id": "PAT-001",
                                    "email": "john@example.com",
                                    "phone": "+15125551234",
                                    "notes": "Interested in veneers, consultation on 3/20",
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {"description": "Patient created"},
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                    },
                },
            },
            "/patients/{patient_id}": {
                "get": {
                    "tags": ["👤 Patients"],
                    "summary": "Get Patient",
                    "description": "**Retrieve a single patient by ID.** Returns 404 if the patient doesn't exist or belongs to a different clinic.",
                    "responses": {
                        "200": {"description": "Patient details"},
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                },
                "put": {
                    "tags": ["👤 Patients"],
                    "summary": "Update Patient",
                    "description": "**Update patient fields.** Partial updates supported -- only include fields you want to change.",
                    "responses": {
                        "200": {"description": "Updated patient"},
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                },
            },
        }
    }
