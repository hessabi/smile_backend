"""
Image endpoints OpenAPI documentation
"""


def get_images_openapi_docs():
    return {
        "paths": {
            "/images/upload-url": {
                "post": {
                    "tags": ["📸 Images"],
                    "summary": "Get Signed Upload URL",
                    "description": """
**Generate a signed GCS URL for direct image upload from the client**

The frontend uses this URL to upload the image directly to Google Cloud Storage,
bypassing the backend for large file transfers.

**Flow:**
1. Client requests a signed upload URL
2. Backend generates a GCS signed PUT URL (15-minute expiry)
3. Client uploads the image directly to GCS using the signed URL
4. Client uses the returned `image_key` in subsequent API calls

**Purpose values:** `before` (patient photo), `post_procedure` (post-op photo)

**Accepted content types:** `image/jpeg`, `image/png`, `image/webp`

**Bucket structure:** `clinics/{clinic_id}/{purpose}/{uuid}.jpg`
                    """,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "example": {
                                    "content_type": "image/jpeg",
                                    "purpose": "before",
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Signed upload URL and storage key",
                            "content": {
                                "application/json": {
                                    "example": {
                                        "upload_url": "https://storage.googleapis.com/smilepreview-images/clinics/...?X-Goog-Signature=...",
                                        "image_key": "clinics/660e8400.../before/770e8400....jpg",
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Invalid purpose or content type",
                        },
                    },
                }
            },
            "/images/{image_key}": {
                "get": {
                    "tags": ["📸 Images"],
                    "summary": "Get Signed Download URL",
                    "description": """
**Generate a signed GCS URL for downloading an image**

Returns a time-limited download URL (15-minute expiry). The `image_key` is the
path-encoded storage key returned from upload or simulation endpoints.

**Security:** Only allows access to images within the authenticated user's clinic
storage path. Returns 403 if the image key doesn't match the user's clinic.
                    """,
                    "responses": {
                        "200": {
                            "description": "Signed download URL",
                            "content": {
                                "application/json": {
                                    "example": {
                                        "download_url": "https://storage.googleapis.com/smilepreview-images/clinics/...?X-Goog-Signature=...",
                                    }
                                }
                            },
                        },
                        "403": {"$ref": "#/components/responses/Forbidden"},
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                }
            },
        }
    }
