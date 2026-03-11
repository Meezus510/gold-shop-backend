from app.services.metals_price_service import GRAMS_PER_TROY_OZ, get_spot_price


def calculate_market_rate(
    api_symbol: str,
    weight_grams: float,
    purity_karat: float,
    purity_denominator: int,
) -> tuple[float, float] | tuple[None, None]:
    """
    Returns (spot_price_per_oz, market_rate_usd) or (None, None) on failure.
    market_rate = (weight_grams / 31.1035) * spot_price * (purity_karat / purity_denominator)
    """
    spot_price = get_spot_price(api_symbol)
    if spot_price is None:
        return None, None
    weight_oz = weight_grams / GRAMS_PER_TROY_OZ
    purity_ratio = purity_karat / purity_denominator
    market_rate = round(weight_oz * spot_price * purity_ratio, 2)
    return spot_price, market_rate


def calculate_item_price(
    api_symbol: str,
    weight_grams: float,
    purity_karat: float,
    purity_denominator: int,
    price_multiplier: float,
    flat_markup: float = 0.0,
) -> float | None:
    """
    Calculates listing price using current spot price:
      market_rate   = (weight_grams / 31.1035) * spot_price * (purity_karat / purity_denominator)
      listing_price = market_rate * price_multiplier + flat_markup

    Returns None when spot price cannot be fetched.
    """
    _, market_rate = calculate_market_rate(api_symbol, weight_grams, purity_karat, purity_denominator)
    if market_rate is None:
        return None
    return round(market_rate * price_multiplier + (flat_markup or 0.0), 2)
