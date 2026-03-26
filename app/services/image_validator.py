import base64
import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GEMINI_FLASH_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)

VALIDATION_PROMPT = """Analyze this image. Does it clearly show a human face with visible teeth (smiling or mouth open)?

Reply ONLY with this JSON format, no other text:
{"valid": true, "reason": "Face with visible teeth detected"}
or
{"valid": false, "reason": "<specific reason>"}

Reject if:
- No human face is present
- Face is present but teeth are not visible (mouth closed)
- Image is too blurry, dark, or low quality to see teeth clearly
- Image contains non-human subjects (animals, objects, landscapes)
- Image is a drawing, illustration, or x-ray (not a photo)"""


class ValidationResult:
    def __init__(self, valid: bool, reason: str | None = None):
        self.valid = valid
        self.reason = reason


async def validate_dental_image(image_bytes: bytes) -> ValidationResult:
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    url = GEMINI_FLASH_URL.format(model=settings.gemini_flash_model)

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": b64_image,
                        }
                    },
                    {"text": VALIDATION_PROMPT},
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url,
                headers={"x-goog-api-key": settings.gemini_api_key},
                json=payload,
            )
    except (httpx.TimeoutException, httpx.HTTPError):
        logger.warning("Image validation request failed, allowing image through")
        return ValidationResult(valid=True)

    if response.status_code >= 400:
        logger.warning("Image validation API error %d, allowing image through", response.status_code)
        return ValidationResult(valid=True)

    try:
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(text)
        valid = result.get("valid", True)
        reason = result.get("reason")
    except (KeyError, IndexError, json.JSONDecodeError, TypeError):
        logger.warning("Could not parse validation response, allowing image through")
        return ValidationResult(valid=True)

    if not valid:
        logger.info("Image rejected: %s", reason)
        return ValidationResult(
            valid=False,
            reason=reason or "Please upload a clear photo of the patient's face with teeth visible.",
        )

    return ValidationResult(valid=True)
