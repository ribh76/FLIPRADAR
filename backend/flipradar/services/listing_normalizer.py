import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

RawListing = dict[str, Any]
NormalizedListing = dict[str, Any]

_CURRENCY_ALIASES = {
    "$": "USD",
    "US$": "USD",
    "USD$": "USD",
    "CA$": "CAD",
    "C$": "CAD",
    "£": "GBP",
    "€": "EUR",
}
_FREE_SHIPPING_VALUES = {"free", "free shipping", "included", "included shipping"}


def normalize(raw_listings: list[RawListing]) -> list[NormalizedListing]:
    normalized = []
    for raw_listing in raw_listings:
        normalized_listing = normalize_listing(raw_listing)
        if normalized_listing is not None:
            normalized.append(normalized_listing)
    return normalized


def normalize_listing(raw_listing: RawListing) -> NormalizedListing | None:
    marketplace = _clean_text(raw_listing.get("marketplace"))
    if marketplace == "ebay":
        return _normalize_ebay_listing(raw_listing)
    if marketplace == "bricklink":
        return _normalize_bricklink_listing(raw_listing)
    return None


def _normalize_ebay_listing(raw_listing: RawListing) -> NormalizedListing | None:
    return _build_listing(
        marketplace="ebay",
        external_listing_id=raw_listing.get("external_listing_id")
        or raw_listing.get("id")
        or raw_listing.get("item_id"),
        price=_first_present(raw_listing.get("price"), raw_listing.get("unit_price")),
        shipping_price=_first_present(
            raw_listing.get("shipping"), raw_listing.get("shipping_price"), 0
        ),
        condition=raw_listing.get("condition"),
        title=raw_listing.get("title"),
        listing_url=raw_listing.get("listing_url") or raw_listing.get("url"),
        seller=raw_listing.get("seller") or raw_listing.get("seller_name"),
        currency=raw_listing.get("currency") or raw_listing.get("currency_code"),
        raw_payload=raw_listing,
    )


def _normalize_bricklink_listing(raw_listing: RawListing) -> NormalizedListing | None:
    return _build_listing(
        marketplace="bricklink",
        external_listing_id=raw_listing.get("external_listing_id")
        or raw_listing.get("listing_id")
        or raw_listing.get("id"),
        price=_first_present(raw_listing.get("price"), raw_listing.get("unit_price")),
        shipping_price=_first_present(
            raw_listing.get("shipping_price"), raw_listing.get("shipping"), 0
        ),
        condition=raw_listing.get("condition"),
        title=raw_listing.get("title") or raw_listing.get("item_name"),
        listing_url=raw_listing.get("listing_url") or raw_listing.get("url"),
        seller=raw_listing.get("seller") or raw_listing.get("seller_name"),
        currency=raw_listing.get("currency") or raw_listing.get("currency_code"),
        raw_payload=raw_listing,
    )


def _build_listing(
    *,
    marketplace: Any,
    external_listing_id: Any,
    price: Any,
    shipping_price: Any,
    condition: Any,
    title: Any,
    listing_url: Any,
    seller: Any,
    currency: Any,
    raw_payload: RawListing,
) -> NormalizedListing | None:
    normalized_marketplace = _clean_text(marketplace)
    normalized_price = _to_money(price)
    normalized_shipping = _to_shipping_money(shipping_price)
    normalized_title = _clean_display_text(title)
    normalized_url = _clean_display_text(listing_url)

    if not all(
        [
            normalized_marketplace,
            external_listing_id,
            normalized_price is not None,
            normalized_shipping is not None,
            normalized_title,
            normalized_url,
        ]
    ):
        return None

    return {
        "marketplace": normalized_marketplace,
        "external_listing_id": str(external_listing_id),
        "price": normalized_price,
        "shipping_price": normalized_shipping,
        "condition": _normalize_condition(condition),
        "is_complete": _is_complete(condition, title),
        "is_sealed": _is_sealed(condition, title),
        "title": normalized_title,
        "listing_url": normalized_url,
        "seller": _clean_display_text(seller),
        "currency": _normalize_currency(currency),
        "raw_payload": raw_payload,
    }


def _to_money(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        cleaned_value = re.sub(r"[^0-9.+-]", "", str(value).replace(",", ""))
        money = Decimal(cleaned_value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation, ValueError:
        return None
    return money if money >= 0 else None


def _to_shipping_money(value: Any) -> Decimal | None:
    if _clean_text(value) in _FREE_SHIPPING_VALUES:
        return Decimal("0.00")
    return _to_money(value)


def _normalize_condition(value: Any) -> str:
    condition = _clean_text(value)
    if condition in {
        "new",
        "n",
        "sealed",
        "new sealed",
        "brand new",
        "new other",
        "new in box",
        "nisb",
    }:
        return "new"
    if condition in {
        "used",
        "u",
        "pre-owned",
        "preowned",
        "open box",
        "complete",
    }:
        return "used"
    return "unknown"


def _is_complete(condition: Any, title: Any) -> bool | None:
    text = f"{_clean_text(condition)} {_clean_text(title)}"
    if any(
        token in text
        for token in ("incomplete", "missing", "no minifig", "without minifig")
    ):
        return False
    if "complete" in text:
        return True
    return None


def _is_sealed(condition: Any, title: Any) -> bool:
    text = f"{_clean_text(condition)} {_clean_text(title)}"
    return any(token in text for token in ("sealed", "nisb", "new in box"))


def _normalize_currency(value: Any) -> str:
    currency = _clean_display_text(value).upper().replace(" ", "")
    if not currency:
        return "USD"
    if currency in _CURRENCY_ALIASES:
        return _CURRENCY_ALIASES[currency]
    return currency if re.fullmatch(r"[A-Z]{3}", currency) else "USD"


def _first_present(*values: Any) -> Any:
    return next((value for value in values if value is not None and value != ""), None)


def _clean_text(value: Any) -> str:
    return _clean_display_text(value).lower()


def _clean_display_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
