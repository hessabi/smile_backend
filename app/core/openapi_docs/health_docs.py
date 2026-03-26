"""
Health check endpoint OpenAPI documentation
"""


def get_health_openapi_docs():
    return {
        "paths": {
            "/health": {
                "get": {
                    "tags": ["💚 Health"],
                    "summary": "Health Check",
                    "description": """
**API health check endpoint**

No authentication required. Used by Cloud Run, load balancers, and uptime monitors.

Returns `{"status": "ok"}` when the service is running.
                    """,
                    "responses": {
                        "200": {
                            "description": "Service is healthy",
                            "content": {
                                "application/json": {
                                    "example": {"status": "ok"},
                                }
                            },
                        },
                    },
                }
            },
        }
    }
