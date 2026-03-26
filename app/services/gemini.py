import base64
import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-3.1-flash-image-preview:generateContent"
)

TREATMENT_DESCRIPTIONS = {
    "veneers": "perfect porcelain veneers that look natural and professionally placed",
    "whitening": "professionally whitened teeth that look bright and clean",
    "allon4": "a full set of beautiful, natural-looking dental implant teeth (All-on-4 full arch restoration)",
    "makeover": "a complete smile makeover with perfectly aligned, symmetrical, beautiful teeth",
}

SHADE_DESCRIPTIONS = {
    "subtle": "a natural, subtle shade that matches the person's complexion",
    "natural": "a bright but natural-looking white shade",
    "hollywood": "a bright Hollywood-white shade",
}


def _build_prompt(treatment_type: str, shade: str) -> str:
    treatment_desc = TREATMENT_DESCRIPTIONS.get(treatment_type, treatment_type)
    shade_desc = SHADE_DESCRIPTIONS.get(shade, shade)

    return (
        f"Edit this photo of a person. Replace ONLY their teeth with {treatment_desc} "
        f"in {shade_desc}.\n\n"
        "CRITICAL RULES:\n"
        "- Keep the person's face, skin, eyes, hair, expression, pose, lighting, "
        "and background EXACTLY the same\n"
        "- Do NOT change anything about the person's appearance except the teeth\n"
        "- The teeth should look photorealistic and natural, not artificial or computer-generated\n"
        "- Maintain natural gum line and lip shape\n"
        "- The result should look like a real \"after\" photo from a professional dental procedure\n"
        "- Output a single photorealistic image"
    )


class GeminiResult:
    def __init__(self, image_bytes: bytes | None, error: str | None, elapsed_ms: int, prompt: str):
        self.image_bytes = image_bytes
        self.error = error
        self.elapsed_ms = elapsed_ms
        self.prompt = prompt


async def generate_smile(image_bytes: bytes, treatment_type: str, shade: str) -> GeminiResult:
    prompt = _build_prompt(treatment_type, shade)
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

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
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

    start = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                GEMINI_URL,
                headers={"x-goog-api-key": settings.gemini_api_key},
                json=payload,
            )
    except httpx.TimeoutException:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return GeminiResult(None, "Connection error. Please try again.", elapsed_ms, prompt)
    except httpx.HTTPError:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return GeminiResult(None, "Connection error. Please try again.", elapsed_ms, prompt)

    elapsed_ms = int((time.monotonic() - start) * 1000)

    if response.status_code == 429:
        return GeminiResult(None, "Service temporarily busy. Please try again.", elapsed_ms, prompt)

    if response.status_code >= 400:
        body = response.text
        if "SAFETY" in body.upper():
            return GeminiResult(
                None,
                "Image could not be processed. Try a different photo.",
                elapsed_ms,
                prompt,
            )
        logger.error("Gemini API error %d: %s", response.status_code, body[:500])
        return GeminiResult(None, "Could not generate preview for this photo. Try better lighting.", elapsed_ms, prompt)

    data = response.json()

    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        return GeminiResult(
            None,
            "Could not generate preview for this photo. Try better lighting.",
            elapsed_ms,
            prompt,
        )

    result_image = None
    for part in parts:
        if "inlineData" in part:
            result_image = base64.b64decode(part["inlineData"]["data"])
        elif "text" in part:
            logger.info("Gemini commentary: %s", part["text"][:200])

    if result_image is None:
        return GeminiResult(
            None,
            "Could not generate preview for this photo. Try better lighting.",
            elapsed_ms,
            prompt,
        )

    return GeminiResult(result_image, None, elapsed_ms, prompt)
