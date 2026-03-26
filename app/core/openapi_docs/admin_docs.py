"""
Platform admin endpoints OpenAPI documentation
"""


def get_admin_openapi_docs():
    return {
        "paths": {
            "/admin/clinics": {
                "get": {
                    "tags": ["🔒 Platform Admin"],
                    "summary": "List All Clinics",
                    "description": """
**List every clinic on the platform with aggregate counts**

🔒 **Requires:** `is_platform_admin = true`

Returns all clinics with user count, patient count, simulation count,
subscription status, and trial expiry. Supports search by name and pagination.
                    """,
                    "responses": {
                        "200": {"description": "Paginated clinic list with counts"},
                        "403": {"$ref": "#/components/responses/Forbidden"},
                    },
                }
            },
            "/admin/clinics/{clinic_id}": {
                "get": {
                    "tags": ["🔒 Platform Admin"],
                    "summary": "Get Clinic Detail",
                    "description": "**Get detailed clinic info with aggregate counts.** 🔒 Requires platform admin.",
                    "responses": {
                        "200": {"description": "Clinic detail with counts"},
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                }
            },
            "/admin/users": {
                "get": {
                    "tags": ["🔒 Platform Admin"],
                    "summary": "List All Users",
                    "description": """
**List every user across all clinics**

🔒 **Requires:** `is_platform_admin = true`

Returns users with their clinic name, role, and active status.
Searchable by name or email. Paginated.
                    """,
                    "responses": {
                        "200": {"description": "Paginated user list"},
                        "403": {"$ref": "#/components/responses/Forbidden"},
                    },
                }
            },
            "/admin/patients": {
                "get": {
                    "tags": ["🔒 Platform Admin"],
                    "summary": "List All Patients",
                    "description": """
**List every patient across all clinics**

🔒 **Requires:** `is_platform_admin = true`

Searchable by display name or external ID. Paginated.
                    """,
                    "responses": {
                        "200": {"description": "Paginated patient list"},
                        "403": {"$ref": "#/components/responses/Forbidden"},
                    },
                }
            },
            "/admin/patients/{patient_id}": {
                "get": {
                    "tags": ["🔒 Platform Admin"],
                    "summary": "Get Patient Detail with Simulations",
                    "description": """
**Get a patient's full details including all simulations with signed image URLs**

🔒 **Requires:** `is_platform_admin = true`

Returns patient info, notes, and all simulations with before/result signed URLs.
                    """,
                    "responses": {
                        "200": {"description": "Patient detail with simulation images"},
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                }
            },
        }
    }
