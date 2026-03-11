import logging

import requests

logger = logging.getLogger(__name__)

GOLD_PRICE_API_URL = "https://api.metals.live/v1/spot/gold"


def get_current_gold_price() -> float | None:
    """
    Fetches the current spot price of gold (USD per troy oz) from metals.live.
    Returns None if the request fails so callers can handle gracefully.
    """
    try:
        response = requests.get(GOLD_PRICE_API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        # metals.live returns a list: [{"gold": <price>}]
        if isinstance(data, list) and data:
            return float(data[0].get("gold", 0))
        # fallback if shape is a plain dict
        if isinstance(data, dict):
            return float(data.get("gold", 0))
    except Exception as exc:
        logger.error("Failed to fetch gold price: %s", exc)
    return None


GRAMS_PER_TROY_OZ = 31.1035


def calculate_price(weight_grams: float, price_multiplier: float) -> float | None:
    """
    price = (weight_grams / 31.1035) * gold_price_per_oz * price_multiplier
    Returns None when the gold price cannot be fetched.
    """
    gold_price = get_current_gold_price()
    if gold_price is None:
        return None
    weight_oz = weight_grams / GRAMS_PER_TROY_OZ
    return round(weight_oz * gold_price * price_multiplier, 2)
