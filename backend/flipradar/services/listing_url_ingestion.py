"""Validation and canonicalization for marketplace listing URLs."""

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urljoin, urlparse

import requests

from flipradar.services.errors import ServiceValidationError

EBAY_ITEM_ID = re.compile(r"^/itm/(?:[^/]+/)?(\d{9,20})(?:/|$)", re.IGNORECASE)
BRICKLINK_INVENTORY_ID = re.compile(
    r"(?:^|[&#])(?:O|inventoryID)=(\d+)(?:&|$)", re.IGNORECASE
)


@dataclass(frozen=True)
class CanonicalListingUrl:
    provider: str
    external_listing_id: str
    url: str
    is_shortened: bool = False


def normalize_listing_url(value: str) -> CanonicalListingUrl:
    """Accept only public HTTPS eBay/BrickLink listing URLs; never resolve DNS."""
    if not value or len(value) > 1000 or any(ord(char) < 32 for char in value):
        raise ServiceValidationError("Listing URL is malformed")
    parsed = urlparse(value.strip())
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ServiceValidationError("Listing URL must be a public HTTPS provider URL")
    host = parsed.hostname.lower().rstrip(".")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ServiceValidationError("IP-address listing URLs are not allowed")
    if host == "ebay.to":
        if not parsed.path or parsed.path == "/":
            raise ServiceValidationError("eBay short URL is missing its target")
        return CanonicalListingUrl("ebay", "", value.strip(), is_shortened=True)
    if _is_ebay_host(host):
        match = EBAY_ITEM_ID.match(parsed.path)
        if not match:
            raise ServiceValidationError("eBay URL must identify a listing")
        listing_id = match.group(1)
        return CanonicalListingUrl(
            "ebay", listing_id, f"https://www.ebay.com/itm/{listing_id}"
        )
    if host in {"bricklink.com", "www.bricklink.com"}:
        listing_id = _bricklink_listing_id(parsed)
        if not listing_id:
            raise ServiceValidationError(
                "BrickLink URL must identify an inventory listing"
            )
        return CanonicalListingUrl(
            "bricklink",
            listing_id,
            f"https://www.bricklink.com/v2/catalog/catalogitem.page#T=S&O={listing_id}",
        )
    raise ServiceValidationError("Only eBay and BrickLink listing URLs are supported")


def resolve_shortened_url(
    short_url: str, *, timeout_seconds: float
) -> CanonicalListingUrl:
    """Resolve only the eBay-owned redirect chain, then reapply the strict allowlist."""
    current = short_url
    for _ in range(4):
        try:
            response = requests.head(
                current, allow_redirects=False, timeout=timeout_seconds
            )
        except requests.Timeout as exc:
            raise ServiceValidationError("eBay short URL resolution timed out") from exc
        if response.is_redirect:
            location = response.headers.get("Location")
            if not location:
                raise ServiceValidationError("eBay short URL redirect is invalid")
            target = normalize_listing_url(urljoin(current, location))
            if not target.is_shortened:
                return target
            current = target.url
            continue
        return normalize_listing_url(current)
    raise ServiceValidationError("eBay short URL has too many redirects")


def _is_ebay_host(host: str) -> bool:
    # Supports www/mobile and regional eBay domains while rejecting lookalikes.
    return bool(
        re.fullmatch(
            r"(?:www\.|m\.)?ebay\.(?:com|[a-z]{2}|com\.[a-z]{2}|co\.[a-z]{2})", host
        )
    )


def _bricklink_listing_id(parsed) -> str | None:
    source = parsed.fragment
    match = BRICKLINK_INVENTORY_ID.search(source)
    if match:
        return match.group(1)
    for key in ("inventoryID", "O"):
        value = parse_qs(parsed.query).get(key, [None])[0]
        if value and value.isdigit():
            return value
    return None
