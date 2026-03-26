from fastapi import FastAPI

from app.core.openapi_docs import (
    get_common_responses,
    get_enhanced_openapi_docs,
    get_openapi_security_schemes,
    get_openapi_tags,
)


def create_custom_openapi(app: FastAPI):
    """Return a closure that generates a custom OpenAPI schema for the given app."""

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        from fastapi.openapi.utils import get_openapi

        openapi_schema = get_openapi(
            title="SmilePreview API",
            version="1.0.0",
            description="""
## 😁 SmilePreview API - Dental Smile Visualization Platform

### Overview
SmilePreview is a SaaS tool for dental professionals that uses AI to generate
realistic smile transformations. Staff can upload a patient photo, select a
treatment type and shade, and receive a photorealistic "after" preview in seconds.

Built for dental clinics, DSOs, and cosmetic dentistry practices.

### Core Workflow
1. **Register** your clinic and create your owner account
2. **Add patients** with display names (privacy-first -- no full names required)
3. **Upload a photo** via signed GCS URL (client uploads directly to cloud storage)
4. **Generate a simulation** -- the API calls Gemini Vision to produce the preview
5. **Share results** -- email the preview to the patient or generate a public share link
6. **Compare outcomes** -- upload post-procedure photos linked to the original simulation

### Authentication
All endpoints (except `/health` and `/auth/register`) require a Firebase ID token:

```
Authorization: Bearer <firebase_id_token>
```

The frontend handles login/signup via Firebase Auth (email/password or Google SSO).
The backend verifies tokens using the Firebase Admin SDK. Token refresh is handled
automatically by the Firebase client SDK.

### Clinic Isolation
Every query filters by the authenticated user's `clinic_id`. There is no way to
access another clinic's patients, images, or simulations. The `clinic_id` is never
accepted as a request parameter -- it always comes from the authenticated user's record.

### User Roles
| Role | Permissions |
|------|------------|
| `owner` | Full access. Can manage team, view audit logs, update clinic settings. |
| `office_admin` | Same as owner except cannot assign the owner role. |
| `provider` | Create patients, run simulations, share results. |
| `nurse` | Upload photos, view patients, assist with simulations. |

### Image Security
- All images are stored in Google Cloud Storage with **no public URLs**
- Access is via **signed URLs that expire in 15 minutes** (HIPAA requirement)
- Image keys are validated to ensure they belong to the requesting user's clinic
- The client never sees permanent storage URLs

### AI Simulation
- Powered by **Google Gemini Vision API** (gemini-3.1-flash-image-preview)
- Treatment types: veneers, whitening, All-on-4, full makeover
- Shade options: subtle, natural, Hollywood white
- Generation takes 15-30 seconds (synchronous)
- Failed simulations are recorded with error messages for debugging

### Share & Email
- **Share links** are public, time-limited (default 7 days), and cryptographically random
- **Branded emails** include inline before/preview images, a share link button, and a PDF attachment
- **PDF reports** show before and preview images side by side with clinic branding and disclaimer

### Audit Trail
Every state-changing action writes an append-only audit log entry with:
- Who performed the action (user ID)
- What was done (action type, resource type, resource ID)
- When it happened (UTC timestamp)
- Context (IP address, user agent)

### Subscription & Billing
- **Stripe-managed** -- plans and prices configured in Stripe Dashboard
- **Two options:** monthly or annual subscription
- **Checkout:** Stripe Checkout redirect (no custom payment page)
- **Customer portal:** Stripe-hosted portal for updating payment, switching plans, canceling
- **Webhooks:** `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`
- **Trial:** 3-day free trial on registration, limited to 1 simulation per day
- **Enforcement:** Expired/canceled subscriptions are blocked from all core endpoints (patients, simulations, images, team). Auth, clinic profile, subscription management, and public share links remain accessible.

### Infrastructure
- **Runtime:** Python 3.12+ / FastAPI
- **Database:** PostgreSQL 15 on Cloud SQL (async via SQLAlchemy + asyncpg)
- **Storage:** Google Cloud Storage
- **Auth:** Firebase Admin SDK
- **AI:** Google Gemini API
- **Email:** Resend
- **Deployment:** Docker on Google Cloud Run

### Support & Resources
- **Documentation:** Available at `/docs` or `/redoc`
- **Contact:** support@smilepreview.com
- **Website:** https://smilepreview.com
            """,
            routes=app.routes,
            tags=get_openapi_tags(),
        )

        enhanced_docs = get_enhanced_openapi_docs()

        for key, value in enhanced_docs.items():
            if key in openapi_schema:
                if isinstance(openapi_schema[key], dict) and isinstance(value, dict):
                    openapi_schema[key].update(value)
                elif isinstance(openapi_schema[key], list) and isinstance(value, list):
                    openapi_schema[key].extend(value)
            else:
                openapi_schema[key] = value

        if "components" not in openapi_schema:
            openapi_schema["components"] = {}

        openapi_schema["components"]["securitySchemes"] = get_openapi_security_schemes()

        if "responses" not in openapi_schema["components"]:
            openapi_schema["components"]["responses"] = {}

        openapi_schema["components"]["responses"].update(get_common_responses())

        openapi_schema["info"]["contact"] = {
            "name": "SmilePreview Support",
            "url": "https://smilepreview.com/support",
            "email": "support@smilepreview.com",
        }

        openapi_schema["info"]["license"] = {
            "name": "Proprietary",
            "url": "https://smilepreview.com/terms",
        }

        openapi_schema["externalDocs"] = {
            "description": "SmilePreview Documentation",
            "url": "https://docs.smilepreview.com",
        }

        openapi_schema["servers"] = [
            {
                "url": "https://api.smilepreview.com",
                "description": "Production server",
            },
            {
                "url": "http://localhost:8080",
                "description": "Development server",
            },
        ]

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    return custom_openapi
