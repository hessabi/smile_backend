"""
Simulation endpoints OpenAPI documentation
"""


def get_simulations_openapi_docs():
    return {
        "paths": {
            "/simulations": {
                "post": {
                    "tags": ["😁 Simulations"],
                    "summary": "Create Smile Simulation",
                    "description": """
**Generate an AI-powered smile preview**

This is the core endpoint of SmilePreview. It takes a patient's before photo
and generates a realistic smile transformation using the Gemini Vision API.

**Flow:**
1. Validates patient belongs to your clinic
2. Validates the image key belongs to your clinic's storage
3. Creates a simulation record with status `processing`
4. Downloads the before image from GCS
5. Calls the Gemini API with the photo and treatment parameters
6. Uploads the result image to GCS
7. Returns the simulation with signed download URLs

**This is a synchronous call that takes 15-30 seconds.** The frontend should
show a loading state while waiting.

**Treatment Types:** `veneers`, `whitening`, `allon4`, `makeover`

**Shade Options:** `subtle`, `natural`, `hollywood`

**On failure:** The simulation record is saved with `status: "failed"` and
an `error_message` explaining what went wrong.
                    """,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "example": {
                                    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                                    "before_image_key": "clinics/660e8400.../before/770e8400....jpg",
                                    "treatment_type": "veneers",
                                    "shade": "natural",
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Simulation created (may be completed or failed)",
                            "content": {
                                "application/json": {
                                    "example": {
                                        "id": "880e8400-e29b-41d4-a716-446655440000",
                                        "clinic_id": "660e8400-e29b-41d4-a716-446655440000",
                                        "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                                        "treatment_type": "veneers",
                                        "shade": "natural",
                                        "status": "completed",
                                        "generation_time_ms": 18432,
                                        "before_image_url": "https://storage.googleapis.com/...",
                                        "result_image_url": "https://storage.googleapis.com/...",
                                        "created_at": "2026-03-24T10:05:00Z",
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Invalid treatment type or shade",
                            "content": {
                                "application/json": {
                                    "example": {"detail": "Invalid treatment type"},
                                }
                            },
                        },
                        "403": {
                            "description": "Image key belongs to another clinic",
                            "content": {
                                "application/json": {
                                    "example": {"detail": "Invalid image key"},
                                }
                            },
                        },
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                }
            },
            "/simulations/{simulation_id}": {
                "get": {
                    "tags": ["😁 Simulations"],
                    "summary": "Get Simulation",
                    "description": "**Retrieve a simulation by ID with signed download URLs for before and result images.** URLs expire in 15 minutes.",
                    "responses": {
                        "200": {"description": "Simulation details with signed image URLs"},
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                },
            },
            "/simulations/{simulation_id}/full": {
                "get": {
                    "tags": ["😁 Simulations"],
                    "summary": "Get Full Simulation (with Post-Op)",
                    "description": """
**Retrieve a simulation with before, AI preview, and post-procedure images**

Returns the same data as `GET /simulations/{id}` plus a `post_procedure_image_url`
if a post-procedure photo has been linked to this simulation.

Useful for the patient comparison view showing all three stages.
                    """,
                    "responses": {
                        "200": {"description": "Full simulation with all image URLs"},
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                },
            },
            "/simulations/{simulation_id}/pdf": {
                "get": {
                    "tags": ["😁 Simulations"],
                    "summary": "Download PDF Report",
                    "description": """
**Generate and download a one-pager PDF report**

The PDF includes:
- Clinic name and provider name
- Patient name, treatment type, shade, and date
- Before and AI preview images side by side
- Post-procedure photo (if linked) for a three-image layout
- Legal disclaimer

Returns `application/pdf` binary. Only works for completed simulations.
                    """,
                    "responses": {
                        "200": {
                            "description": "PDF file download",
                            "content": {"application/pdf": {}},
                        },
                        "400": {
                            "description": "Simulation not completed",
                            "content": {
                                "application/json": {
                                    "example": {"detail": "Can only generate PDF for completed simulations"},
                                }
                            },
                        },
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                },
            },
            "/simulations/{simulation_id}/send-email": {
                "post": {
                    "tags": ["😁 Simulations"],
                    "summary": "Email Smile Preview to Patient",
                    "description": """
**Send a branded email with the smile preview to the patient**

Generates a share link, creates a PDF attachment, and sends a branded HTML email
via Resend. Uses the patient's stored email unless an override is provided.

**Email includes:**
- Before and preview images inline
- Button linking to the public share page
- PDF attachment with the full report
- Clinic branding and disclaimer
- Share link expires in 7 days

**Requires:** Patient must have an email on file, or provide one in the request body.
                    """,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "email": {
                                            "type": "string",
                                            "format": "email",
                                            "description": "Override email (uses patient's stored email if omitted)",
                                            "example": "patient@example.com",
                                        },
                                    },
                                },
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Email sent",
                            "content": {
                                "application/json": {
                                    "example": {"detail": "Email sent successfully", "to": "patient@example.com"},
                                }
                            },
                        },
                        "400": {
                            "description": "No email available or simulation not completed",
                            "content": {
                                "application/json": {
                                    "example": {"detail": "No email address provided and patient has no email on file"},
                                }
                            },
                        },
                    },
                },
            },
            "/simulations/{simulation_id}/share": {
                "post": {
                    "tags": ["🔗 Share"],
                    "summary": "Create Share Link",
                    "description": """
**Generate a public share link for a completed simulation**

Creates a unique, time-limited token that allows anyone with the link to view
the before and preview images without authentication.

**Security:**
- Tokens are cryptographically random (48 bytes, URL-safe)
- Links expire after the configured number of days (default: 7)
- Only completed simulations can be shared

The share URL format is: `{SHARE_BASE_URL}/share/{token}`
                    """,
                    "responses": {
                        "201": {
                            "description": "Share link created",
                            "content": {
                                "application/json": {
                                    "example": {
                                        "id": "990e8400-e29b-41d4-a716-446655440000",
                                        "share_url": "https://app.smilepreview.com/share/abc123...",
                                        "expires_at": "2026-03-31T10:00:00Z",
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Simulation not completed",
                        },
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                },
            },
            "/patients/{patient_id}/simulations": {
                "get": {
                    "tags": ["😁 Simulations"],
                    "summary": "List Patient Simulations",
                    "description": """
**List all simulations for a specific patient with pagination**

Returns simulations ordered by most recent first, each with signed download URLs.

**Query Parameters:**
- `limit` - Results per page (1-100, default 20)
- `offset` - Pagination offset (default 0)
                    """,
                    "responses": {
                        "200": {"description": "List of simulations with signed image URLs"},
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                },
            },
        }
    }
