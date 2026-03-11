from app.services.metals_price_service import GRAMS_PER_TROY_OZ, get_spot_price


def calculate_item_price(
    api_symbol: str,
    weight_grams: float,
    purity_karat: float,
    purity_denominator: int,
    price_multiplier: float,
) -> float | None:
    """
    Calculates item price using current spot price:
      price = (weight_grams / 31.1035) * spot_price_per_oz
              * (purity_karat / purity_denominator) * price_multiplier

    Returns None when spot price cannot be fetched.
    """
    spot_price = get_spot_price(api_symbol)
    if spot_price is None:
        return None
    weight_oz = weight_grams / GRAMS_PER_TROY_OZ
    purity_ratio = purity_karat / purity_denominator
    return round(weight_oz * spot_price * purity_ratio * price_multiplier, 2)
