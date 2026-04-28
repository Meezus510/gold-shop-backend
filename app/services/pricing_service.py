from app.services.metals_price_service import GRAMS_PER_TROY_OZ, get_spot_price


def calculate_market_rate(
    api_symbol: str,
    weight_grams: float,
    purity_karat: float,
    purity_denominator: int,
) -> tuple[float, float] | tuple[None, None]:
    """
    Returns (spot_price_per_oz, base_market_price_usd) or (None, None) on failure.
    base_market_price = (weight_grams / 31.1035) * spot_price * (purity_karat / purity_denominator)
    """
    spot_price = get_spot_price(api_symbol)
    if spot_price is None:
        return None, None
    weight_oz    = weight_grams / GRAMS_PER_TROY_OZ
    purity_ratio = purity_karat / purity_denominator
    base_market_price = round(weight_oz * spot_price * purity_ratio, 2)
    return spot_price, base_market_price


def compute_listed_prices(
    api_symbol: str,
    weight_grams: float,
    purity_karat: float,
    purity_denominator: int,
    markup_flat: float,
    markup_loan: float,
) -> tuple[float, float, float] | tuple[None, None, None]:
    """
    Returns (base_market_price, listed_price_flat, listed_price_loan) or (None, None, None).

    listed_price_flat = max(base_market_price + markup_flat, base_market_price * 1.1)
    listed_price_loan = listed_price_flat + markup_loan
    """
    _, base_market_price = calculate_market_rate(
        api_symbol, weight_grams, purity_karat, purity_denominator
    )
    if base_market_price is None:
        return None, None, None
    listed_flat = round(max(base_market_price + markup_flat, base_market_price * 1.1), 2)
    listed_loan = round(listed_flat + max(markup_loan, 0), 2)
    return base_market_price, listed_flat, listed_loan
