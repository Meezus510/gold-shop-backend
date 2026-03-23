"""
Claude API integration for batch image processing.

Two-step flow:
  1. extract_rows_from_image()  — Vision call: OCR the purchase sheet → raw row dicts
  2. enrich_rows()              — Text call: split description, translate ES→EN, infer category
"""
import base64
import json
import logging

import anthropic

from app.config.settings import settings

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None

SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

VALID_CATEGORIES = {
    "ring", "necklace", "bracelet", "earrings", "pendant",
    "chain", "bangle", "brooch", "set", "other", "broqueles",
}

# Default weight (grams) applied when a category has no weight info
CATEGORY_DEFAULT_WEIGHT: dict[str, float] = {
    "broqueles": 0.2,
}


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def extract_rows_from_image(image_bytes: bytes, content_type: str) -> list[dict]:
    """
    Sends the purchase sheet image to Claude Vision and returns a list of raw row dicts.

    Each dict contains the fields as they appear in the image (may be None if unreadable):
      purchase_date, purchase_location, qty, description_es,
      cost, weight_grams, listed_price_flat, listed_price_loan
    """
    if content_type not in SUPPORTED_MEDIA_TYPES:
        raise ValueError(f"Unsupported image type: {content_type}")

    b64_data = base64.standard_b64encode(image_bytes).decode()

    prompt = (
        "Extract the jewelry inventory table from this image.\n\n"
        "The sheet header may contain a date (purchase_date) and a supplier name (purchase_location).\n"
        "Each data row has these columns in order:\n"
        "  1. qty + description_es (e.g. '1- cadena blanca 20\"')\n"
        "  2. cost — what was paid\n"
        "  3. weight_grams\n"
        "  4. A calculated column — IGNORE this\n"
        "  5. Price range written as 'flat - loan' (e.g. '590-770' means flat=590, loan=770)\n\n"
        "Return a JSON object with two keys:\n"
        "  'purchase_date': string YYYY-MM-DD from the sheet header, or null\n"
        "  'purchase_location': supplier name from the sheet header, or null\n"
        "  'rows': array of row objects, each with:\n"
        "    - qty: integer\n"
        "    - description_es: item description exactly as written\n"
        "    - cost: number\n"
        "    - weight_grams: number\n"
        "    - listed_price_flat: first number in the price range\n"
        "    - listed_price_loan: second number in the price range\n\n"
        "Rules:\n"
        "- Only extract rows with actual item data — skip blank or illegible rows.\n"
        "- Use null for any cell that is blank or unreadable.\n"
        "- Return only valid JSON, no markdown, no explanation."
    )

    message = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": content_type,
                        "data": b64_data,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )

    raw_text = message.content[0].text.strip()
    # Strip markdown code fences if Claude wrapped the JSON
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    parsed = json.loads(raw_text)

    # Claude returns an object with purchase_date, purchase_location, and rows
    if isinstance(parsed, dict):
        rows = parsed.get("rows", [])
        # Stamp sheet-level fields onto every row so enrichment has them
        sheet_date     = parsed.get("purchase_date")
        sheet_location = parsed.get("purchase_location")
        for row in rows:
            row.setdefault("purchase_date",     sheet_date)
            row.setdefault("purchase_location", sheet_location)
    elif isinstance(parsed, list):
        rows = parsed
    else:
        raise ValueError("Claude returned unexpected format")

    logger.info("extract_rows_from_image: extracted %d rows", len(rows))
    return rows


def extract_rows_from_image_na(image_bytes: bytes, content_type: str) -> list[dict]:
    """
    Variant of extract_rows_from_image for non-metal (N/A) purchase sheets.
    Expects columns: description, cost, price.  No weight or metal columns.
    """
    if content_type not in SUPPORTED_MEDIA_TYPES:
        raise ValueError(f"Unsupported image type: {content_type}")

    b64_data = base64.standard_b64encode(image_bytes).decode()

    prompt = (
        "Extract the accessories/jewelry inventory table from this image.\n\n"
        "The sheet header may contain a date (purchase_date) and a supplier name (purchase_location).\n"
        "Each data row has:\n"
        "  1. qty + description (e.g. '2- bolsa cafe' or '1- aretes perla')\n"
        "  2. cost — what was paid\n"
        "  3. price — the sell/listed price\n\n"
        "Return a JSON object with:\n"
        "  'purchase_date': string YYYY-MM-DD from the sheet header, or null\n"
        "  'purchase_location': supplier name from the sheet header, or null\n"
        "  'rows': array of row objects, each with:\n"
        "    - qty: integer (default 1 if not shown)\n"
        "    - description_es: item description exactly as written\n"
        "    - cost: number or null\n"
        "    - listed_price_flat: sell/listed price or null\n\n"
        "Rules:\n"
        "- Only extract rows with actual item data — skip blank or illegible rows.\n"
        "- Use null for any cell that is blank or unreadable.\n"
        "- Return only valid JSON, no markdown, no explanation."
    )

    message = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": content_type,
                        "data": b64_data,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )

    raw_text = message.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    parsed = json.loads(raw_text)

    if isinstance(parsed, dict):
        rows = parsed.get("rows", [])
        sheet_date     = parsed.get("purchase_date")
        sheet_location = parsed.get("purchase_location")
        for row in rows:
            row.setdefault("purchase_date",     sheet_date)
            row.setdefault("purchase_location", sheet_location)
    elif isinstance(parsed, list):
        rows = parsed
    else:
        raise ValueError("Claude returned unexpected format")

    logger.info("extract_rows_from_image_na: extracted %d rows", len(rows))
    return rows


def enrich_rows(raw_rows: list[dict]) -> list[dict]:
    """
    Takes raw rows from extract_rows_from_image and enriches each one with:
      - name_es, description_es  (split/cleaned from raw description_es)
      - name_en, description_en  (translated)
      - category                 (inferred from description)

    Returns the same list with new keys merged in.
    Rows with a null description_es are skipped (fields left as None).
    """
    # Build numbered list for only rows that have a description
    indexed = [(i, r) for i, r in enumerate(raw_rows) if r.get("description_es")]
    if not indexed:
        return raw_rows

    entries = "\n".join(
        f"{n + 1}. {r['description_es']}"
        for n, (_, r) in enumerate(indexed)
    )

    prompt = (
        "You are processing jewelry inventory entries for a gold shop.\n\n"
        f"For each item below, return a JSON array of {len(indexed)} objects with these keys:\n"
        "- name_es: short item name in Spanish, properly capitalized, max 60 characters\n"
        "- description_es: 1–2 sentence description in Spanish, expanding naturally on the name\n"
        "- name_en: English translation of name_es\n"
        "- description_en: English translation of description_es\n"
        f"- category: one of {sorted(VALID_CATEGORIES)} "
        "(use 'broqueles' for small gold stud earrings typical of Latin American jewelry shops)\n\n"
        f"Raw entries (in order):\n{entries}\n\n"
        "Return only a valid JSON array, no markdown, no explanation."
    )

    message = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = message.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    enriched = json.loads(raw_text)
    if not isinstance(enriched, list) or len(enriched) != len(indexed):
        raise ValueError(
            f"Claude returned {len(enriched) if isinstance(enriched, list) else 'non-list'} "
            f"enriched rows — expected {len(indexed)}"
        )

    for slot, (orig_idx, _) in enumerate(indexed):
        row_enrichment = enriched[slot]
        # Normalise category
        cat = (row_enrichment.get("category") or "other").lower().strip()
        row_enrichment["category"] = cat if cat in VALID_CATEGORIES else "other"
        raw_rows[orig_idx].update(row_enrichment)

    logger.info("enrich_rows: enriched %d rows", len(indexed))
    return raw_rows
