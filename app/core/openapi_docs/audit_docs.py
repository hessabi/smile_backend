"""
Audit log endpoints OpenAPI documentation
"""


def get_audit_openapi_docs():
    return {
        "paths": {
            "/audit-logs": {
                "get": {
                    "tags": ["📊 Audit"],
                    "summary": "List Audit Logs",
                    "description": """
**List all audit log entries for the current clinic**

🔒 **Requires role:** `owner` or `office_admin`

Returns an append-only audit trail of every state-changing action in the clinic.
Each entry records who did what, when, and from where.

**Query Parameters:**
- `limit` - Results per page (1-200, default 50)
- `offset` - Pagination offset (default 0)

**Action format:** `{resource}.{verb}` (e.g., `patient.create`, `simulation.complete`, `team.invite`)

**Fields per entry:**
- `action` - What happened
- `user_id` - Who did it
- `resource_type` / `resource_id` - What was affected
- `details` - Additional context (JSON)
- `ip_address` / `user_agent` - Where it came from
- `created_at` - When it happened (UTC)
                    """,
                    "responses": {
                        "200": {
                            "description": "Paginated audit log",
                            "content": {
                                "application/json": {
                                    "example": {
                                        "logs": [
                                            {
                                                "id": 42,
                                                "clinic_id": "660e8400-e29b-41d4-a716-446655440000",
                                                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                                                "action": "simulation.complete",
                                                "resource_type": "simulation",
                                                "resource_id": "880e8400-e29b-41d4-a716-446655440000",
                                                "details": {"elapsed_ms": 18432},
                                                "ip_address": "192.168.1.1",
                                                "user_agent": "Mozilla/5.0...",
                                                "created_at": "2026-03-24T10:05:30Z",
                                            }
                                        ],
                                        "total": 1,
                                    }
                                }
                            },
                        },
                        "403": {"$ref": "#/components/responses/Forbidden"},
                    },
                }
            },
        }
    }
