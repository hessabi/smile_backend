"""
Team management endpoints OpenAPI documentation
"""


def get_team_openapi_docs():
    return {
        "paths": {
            "/team": {
                "get": {
                    "tags": ["👥 Team"],
                    "summary": "List Team Members",
                    "description": """
**List all users in the current clinic**

🔒 **Requires role:** `owner` or `office_admin`

Returns all team members with their roles and active status, ordered by join date.
                    """,
                    "responses": {
                        "200": {
                            "description": "List of team members",
                            "content": {
                                "application/json": {
                                    "example": [
                                        {
                                            "id": "550e8400-e29b-41d4-a716-446655440000",
                                            "email": "dr.smith@smithdental.com",
                                            "name": "Dr. Sarah Smith",
                                            "role": "owner",
                                            "is_active": True,
                                            "created_at": "2026-03-24T10:00:00Z",
                                            "updated_at": "2026-03-24T10:00:00Z",
                                        },
                                        {
                                            "id": "660e8400-e29b-41d4-a716-446655440000",
                                            "email": "nurse.jones@smithdental.com",
                                            "name": "Maria Jones",
                                            "role": "nurse",
                                            "is_active": True,
                                            "created_at": "2026-03-25T09:00:00Z",
                                            "updated_at": "2026-03-25T09:00:00Z",
                                        },
                                    ]
                                }
                            },
                        },
                        "403": {"$ref": "#/components/responses/Forbidden"},
                    },
                }
            },
            "/team/invite": {
                "post": {
                    "tags": ["👥 Team"],
                    "summary": "Invite Team Member",
                    "description": """
**Create a new user record in the clinic with a specified role**

🔒 **Requires role:** `owner` or `office_admin`

Creates a placeholder user record. The invited user will need to create a Firebase
account and their `firebase_uid` will be linked when they first log in.

**Available Roles:**
- `provider` - Dentist/doctor who creates simulations
- `nurse` - Clinical staff who uploads photos and views patients
- `office_admin` - Front desk/manager with access to audit logs and clinic settings
- `owner` - Full access (only assignable by existing owners)

**Restrictions:**
- Only owners can assign the `owner` role
- Duplicate emails within the same clinic are rejected
                    """,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "example": {
                                    "email": "nurse.jones@smithdental.com",
                                    "name": "Maria Jones",
                                    "role": "nurse",
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {"description": "Team member created"},
                        "400": {
                            "description": "Invalid role or duplicate email",
                            "content": {
                                "application/json": {
                                    "examples": {
                                        "invalid_role": {
                                            "summary": "Role not allowed",
                                            "value": {"detail": "Invalid role. Must be one of: provider, nurse, office_admin, owner"},
                                        },
                                        "duplicate": {
                                            "summary": "Email already in use",
                                            "value": {"detail": "A user with this email already exists in your clinic"},
                                        },
                                    }
                                }
                            },
                        },
                        "403": {"$ref": "#/components/responses/Forbidden"},
                    },
                }
            },
            "/team/{user_id}": {
                "put": {
                    "tags": ["👥 Team"],
                    "summary": "Update Team Member",
                    "description": """
**Update a team member's role or active status**

🔒 **Requires role:** `owner` or `office_admin`

Partial updates supported. You cannot modify your own account via this endpoint.

**Use cases:**
- Change a nurse to office_admin
- Deactivate a departing staff member (`is_active: false`)
- Reactivate a returning staff member
                    """,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "examples": {
                                    "change_role": {
                                        "summary": "Promote to office_admin",
                                        "value": {"role": "office_admin"},
                                    },
                                    "deactivate": {
                                        "summary": "Deactivate user",
                                        "value": {"is_active": False},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Updated team member"},
                        "400": {"description": "Cannot modify your own account"},
                        "403": {"$ref": "#/components/responses/Forbidden"},
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                }
            },
        }
    }
