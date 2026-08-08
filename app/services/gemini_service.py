"""Low-cost Gemini vision analysis for fast Broqueles inventory intake."""

import base64
import logging

import requests

from app.config.settings import settings
from app.schemas.fast_broquel_schema import FastBroquelAnalysis

logger = logging.getLogger(__name__)

_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_FALLBACK_MODEL = "gemini-3.1-flash-lite"


def analyze_broquel_image(image_bytes: bytes, content_type: str) -> FastBroquelAnalysis:
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    prompt = (
        "Create concise bilingual catalog copy for the small stud earrings "
        "(broqueles) shown in this product photo. Describe only visible traits such "
        "as shape, color, setting, motif, and finish. Never claim a specific metal, "
        "karat, gemstone, brand, or authenticity because those cannot be verified "
        "from a photo. Use natural retail language. Return Spanish and English names "
        "of at most 60 characters and one-sentence descriptions."
    )
    schema = FastBroquelAnalysis.model_json_schema()
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {
                    "inlineData": {
                        "mimeType": content_type,
                        "data": base64.b64encode(image_bytes).decode("ascii"),
                    }
                },
                {"text": prompt},
            ],
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 500,
            "responseMimeType": "application/json",
            "responseJsonSchema": schema,
        },
    }

    headers = {
        "x-goog-api-key": settings.GEMINI_API_KEY,
        "Content-Type": "application/json",
    }
    model = settings.FAST_BROQUEL_AI_MODEL
    response = requests.post(
        _API_URL.format(model=model),
        headers=headers,
        json=payload,
        timeout=30,
    )
    if response.status_code == 404 and model != _FALLBACK_MODEL:
        logger.warning(
            "Configured Gemini model %s is unavailable; retrying with %s",
            model,
            _FALLBACK_MODEL,
        )
        response = requests.post(
            _API_URL.format(model=_FALLBACK_MODEL),
            headers=headers,
            json=payload,
            timeout=30,
        )
    response.raise_for_status()
    body = response.json()
    try:
        raw_text = body["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("Gemini returned an unexpected response shape")
        raise ValueError("Image analyzer returned no usable result") from exc

    return FastBroquelAnalysis.model_validate_json(raw_text)
