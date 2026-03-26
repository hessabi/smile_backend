"""
Authentication endpoints OpenAPI documentation
"""


def get_auth_openapi_docs():
    return {
        "paths": {
            "/auth/register": {
                "post": {
                    "tags": ["🔐 Authentication"],
                    "summary": "Register Clinic & Admin User",
                    "description": """
**Onboard a new clinic with its first admin user**

Creates both a clinic record and an owner user in a single transaction.
This is the entry point for new SmilePreview customers.

**No authentication required** - this endpoint is public.

**Flow:**
1. Frontend creates a Firebase account (email/password or Google SSO)
2. Frontend calls this endpoint with the Firebase UID
3. Backend verifies the UID with Firebase Admin SDK
4. Backend creates a clinic and an owner user
5. Returns the user and clinic objects

**Note:** Each Firebase UID can only register once. Subsequent team members
are added via the `/team/invite` endpoint by an owner or office_admin.
                    """,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["firebase_uid", "email", "name", "clinic_name"],
                                    "properties": {
                                        "firebase_uid": {
                                            "type": "string",
                                            "description": "Firebase Authentication UID",
                                            "example": "abc123def456",
                                        },
                                        "email": {
                                            "type": "string",
                                            "format": "email",
                                            "description": "User's email address",
                                            "example": "dr.smith@smithdental.com",
                                        },
                                        "name": {
                                            "type": "string",
                                            "description": "User's full name",
                                            "example": "Dr. Sarah Smith",
                                        },
                                        "clinic_name": {
                                            "type": "string",
                                            "description": "Name of the dental practice",
                                            "example": "Smith Family Dental",
                                        },
                                    },
                                },
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Registration successful",
                            "content": {
                                "application/json": {
                                    "example": {
                                        "user": {
                                            "id": "550e8400-e29b-41d4-a716-446655440000",
                                            "clinic_id": "660e8400-e29b-41d4-a716-446655440000",
                                            "firebase_uid": "abc123def456",
                                            "email": "dr.smith@smithdental.com",
                                            "name": "Dr. Sarah Smith",
                                            "role": "owner",
                                            "is_active": True,
                                            "created_at": "2026-03-24T10:00:00Z",
                                            "updated_at": "2026-03-24T10:00:00Z",
                                        },
                                        "clinic": {
                                            "id": "660e8400-e29b-41d4-a716-446655440000",
                                            "name": "Smith Family Dental",
                                            "plan": "trial",
                                            "settings": {},
                                            "is_active": True,
                                            "created_at": "2026-03-24T10:00:00Z",
                                            "updated_at": "2026-03-24T10:00:00Z",
                                        },
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Invalid Firebase UID or user already registered",
                            "content": {
                                "application/json": {
                                    "examples": {
                                        "invalid_uid": {
                                            "summary": "Firebase UID not valid",
                                            "value": {"detail": "Invalid Firebase UID"},
                                        },
                                        "already_registered": {
                                            "summary": "User already exists",
                                            "value": {"detail": "User already registered"},
                                        },
                                    }
                                }
                            },
                        },
                    },
                }
            },
            "/auth/me": {
                "get": {
                    "tags": ["🔐 Authentication"],
                    "summary": "Get Current User & Clinic",
                    "description": """
**Retrieve the authenticated user's profile and their clinic details**

Returns the full user object and the clinic they belong to.
Used by the frontend on app load to hydrate the session.

**Requires:** `Authorization: Bearer <firebase_id_token>`
                    """,
                    "responses": {
                        "200": {
                            "description": "Current user and clinic",
                        },
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                    },
                }
            },
        }
    }
