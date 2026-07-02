from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

RawListing = dict[str, Any]
NormalizedListing = dict[str, Any]


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
    return _normalize_generic_listing(raw_listing)


def _normalize_ebay_listing(raw_listing: RawListing) -> NormalizedListing | None:
    return _build_listing(
        marketplace="ebay",
        external_listing_id=raw_listing.get("external_listing_id")
        or raw_listing.get("id")
        or raw_listing.get("item_id"),
        price=raw_listing.get("price"),
        shipping_price=raw_listing.get("shipping")
        or raw_listing.get("shipping_price")
        or 0,
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
        price=raw_listing.get("price") or raw_listing.get("unit_price"),
        shipping_price=raw_listing.get("shipping_price")
        or raw_listing.get("shipping")
        or 0,
        condition=raw_listing.get("condition"),
        title=raw_listing.get("title") or raw_listing.get("item_name"),
        listing_url=raw_listing.get("listing_url") or raw_listing.get("url"),
        seller=raw_listing.get("seller") or raw_listing.get("seller_name"),
        currency=raw_listing.get("currency") or raw_listing.get("currency_code"),
        raw_payload=raw_listing,
    )


def _normalize_generic_listing(raw_listing: RawListing) -> NormalizedListing | None:
    return _build_listing(
        marketplace=raw_listing.get("marketplace"),
        external_listing_id=raw_listing.get("external_listing_id")
        or raw_listing.get("listing_id")
        or raw_listing.get("id"),
        price=raw_listing.get("price") or raw_listing.get("unit_price"),
        shipping_price=raw_listing.get("shipping_price")
        or raw_listing.get("shipping")
        or 0,
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
    normalized_shipping = _to_money(shipping_price)
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
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def _normalize_condition(value: Any) -> str:
    condition = _clean_text(value)
    if condition in {"new", "n", "sealed", "new sealed"}:
        return "new"
    if condition in {"used", "u", "pre-owned", "preowned", "open box"}:
        return "used"
    return "unknown"


def _normalize_currency(value: Any) -> str:
    currency = _clean_display_text(value)
    if not currency:
        return "USD"
    return currency.upper()[:3]


def _clean_text(value: Any) -> str:
    return _clean_display_text(value).lower()


def _clean_display_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
