"""
Post-procedure endpoints OpenAPI documentation
"""


def get_post_procedure_openapi_docs():
    return {
        "paths": {
            "/patients/{patient_id}/post-procedure": {
                "post": {
                    "tags": ["📋 Post-Procedure"],
                    "summary": "Create Post-Procedure Record",
                    "description": """
**Upload a post-procedure photo linked to a patient (and optionally a simulation)**

Records the actual result after a dental procedure. Can be linked to the original
AI simulation for a side-by-side comparison of predicted vs. actual outcome.

**Flow:**
1. Upload the photo via `POST /images/upload-url` with `purpose: "post_procedure"`
2. Client uploads to GCS using the signed URL
3. Call this endpoint with the returned `image_key`

**Fields:**
- `image_key` (required) - GCS storage key from the upload step
- `simulation_id` (optional) - Link to the original simulation for comparison
- `procedure_date` (optional) - Date the procedure was performed
- `notes` (optional) - Clinical notes about the outcome

**Security:** Image key must belong to the current clinic's storage path.
                    """,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "example": {
                                    "image_key": "clinics/660e8400.../post-procedure/770e8400....jpg",
                                    "simulation_id": "880e8400-e29b-41d4-a716-446655440000",
                                    "procedure_date": "2026-04-15",
                                    "notes": "Veneers placed, patient satisfied with result",
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Post-procedure record created with signed image URL",
                        },
                        "403": {
                            "description": "Image key belongs to another clinic",
                        },
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                },
                "get": {
                    "tags": ["📋 Post-Procedure"],
                    "summary": "List Post-Procedure Records",
                    "description": """
**List all post-procedure photos for a patient**

Returns records ordered by most recent first, each with a signed download URL
(15-minute expiry). Use this to show the post-op gallery for a patient.
                    """,
                    "responses": {
                        "200": {
                            "description": "List of post-procedure records with signed image URLs",
                        },
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                },
            },
        }
    }
