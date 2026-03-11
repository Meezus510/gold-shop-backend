import logging
import time

import requests

logger = logging.getLogger(__name__)

GRAMS_PER_TROY_OZ = 31.1035

# gold-api.com — free, no auth, returns { "price": <usd_per_troy_oz>, ... }
_API_BASE = "https://api.gold-api.com/price"

# In-memory cache: symbol -> (price_usd_per_oz, fetched_at_monotonic)
_CACHE_TTL_SECONDS = 3600  # re-fetch at most once per hour
_price_cache: dict[str, tuple[float, float]] = {}


def get_spot_price(symbol: str) -> float | None:
    """
    Returns the spot price (USD per troy oz) for the given symbol (XAU, XAG, XPT…).
    Cached in-memory for 1 hour so the external API is only hit once per session hour.
    """
    now = time.monotonic()
    cached = _price_cache.get(symbol)
    if cached is not None:
        price, fetched_at = cached
        if now - fetched_at < _CACHE_TTL_SECONDS:
            logger.debug("Returning cached price for %s: %.4f", symbol, price)
            return price

    price = _fetch(symbol)
    if price is not None:
        _price_cache[symbol] = (price, now)
    return price


def invalidate_cache(symbol: str | None = None) -> None:
    """Force the next call to re-fetch. Pass None to clear all entries."""
    if symbol:
        _price_cache.pop(symbol, None)
    else:
        _price_cache.clear()


def _fetch(symbol: str) -> float | None:
    url = f"{_API_BASE}/{symbol}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        price = data.get("price")
        if price is not None:
            logger.info("Fetched fresh %s price: %.4f USD/oz", symbol, price)
            return float(price)
        logger.warning("Unexpected gold-api.com response for %s: %s", symbol, data)
    except Exception as exc:
        logger.error("Failed to fetch %s spot price: %s", symbol, exc)
    return None
