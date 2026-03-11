import logging

import requests

logger = logging.getLogger(__name__)

GRAMS_PER_TROY_OZ = 31.1035
METALS_LIVE_BASE = "https://api.metals.live/v1/spot"


def get_spot_price(api_symbol: str) -> float | None:
    """
    Fetches the current spot price (USD per troy oz) for a metal from metals.live.
    api_symbol should match the metals.live endpoint segment, e.g. "gold", "silver", "platinum".
    Returns None if the request fails.
    """
    url = f"{METALS_LIVE_BASE}/{api_symbol}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        # metals.live returns a list: [{"gold": <price>}] or [{"silver": <price>}]
        if isinstance(data, list) and data:
            entry = data[0]
            # Try the symbol key first, then grab the first numeric value
            if api_symbol in entry:
                return float(entry[api_symbol])
            values = [v for v in entry.values() if isinstance(v, (int, float))]
            if values:
                return float(values[0])
        if isinstance(data, dict):
            if api_symbol in data:
                return float(data[api_symbol])
            values = [v for v in data.values() if isinstance(v, (int, float))]
            if values:
                return float(values[0])
    except Exception as exc:
        logger.error("Failed to fetch %s spot price: %s", api_symbol, exc)
    return None
