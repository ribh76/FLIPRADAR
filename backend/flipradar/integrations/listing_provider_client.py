"""Official marketplace API clients for single-listing URL ingestion.

This module deliberately never downloads marketplace HTML.  It accepts a
canonical provider URL and uses the provider's documented API instead.
"""

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode

import requests

from flipradar.core.settings import ProviderSettings


class ProviderRetrievalError(Exception):
    pass


class ProviderListingMissingError(ProviderRetrievalError):
    pass


class ProviderTimeoutError(ProviderRetrievalError):
    pass


@dataclass(frozen=True)
class ProviderListing:
    marketplace_name: str
    external_listing_id: str
    title: str
    url: str
    price: str
    shipping_price: str
    currency: str
    condition: str = "unknown"
    listing_status: str = "active"
    seller_name: str | None = None
    is_complete: bool | None = None
    is_sealed: bool | None = None
    raw_payload: dict[str, Any] | None = None


class OfficialListingProviderClient:
    """Retrieves a listing from supported official APIs with bounded requests."""

    def fetch(
        self,
        provider: str,
        listing_id: str,
        canonical_url: str,
        settings: ProviderSettings,
    ) -> ProviderListing:
        if not settings.usable:
            raise ProviderRetrievalError(f"{provider} API is not configured")
        try:
            if provider == "ebay":
                return self._fetch_ebay(listing_id, canonical_url, settings)
            if provider == "bricklink":
                return self._fetch_bricklink(listing_id, canonical_url, settings)
        except requests.Timeout as exc:
            raise ProviderTimeoutError(f"{provider} API timed out") from exc
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ProviderRetrievalError(
                f"{provider} API returned an invalid response"
            ) from exc
        raise ProviderRetrievalError("Unsupported marketplace")

    def _fetch_ebay(
        self, listing_id: str, canonical_url: str, settings: ProviderSettings
    ) -> ProviderListing:
        # eBay Browse API's getItem endpoint is the official item-detail source.
        token_response = requests.post(
            "https://api.ebay.com/identity/v1/oauth2/token",
            auth=(settings.api_key, settings.api_secret),
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            timeout=settings.timeout_seconds,
        )
        if token_response.status_code >= 400:
            raise ProviderRetrievalError("eBay API authentication failed")
        token = token_response.json().get("access_token")
        if not isinstance(token, str) or not token:
            raise ProviderRetrievalError("eBay API returned no access token")
        response = requests.get(
            f"https://api.ebay.com/buy/browse/v1/item/v1|{listing_id}|0",
            headers={"Authorization": f"Bearer {token}"},
            timeout=settings.timeout_seconds,
        )
        if response.status_code == 404:
            raise ProviderListingMissingError("eBay listing is no longer available")
        if response.status_code >= 400:
            raise ProviderRetrievalError("eBay API listing request failed")
        body = response.json()
        price = body.get("price") or {}
        shipping = body.get("shippingOptions") or [{}]
        shipping_cost = shipping[0].get("shippingCost") if shipping else None
        return ProviderListing(
            marketplace_name="ebay",
            external_listing_id=listing_id,
            title=_required_text(body, "title"),
            url=body.get("itemWebUrl", canonical_url),
            price=_money(price),
            shipping_price=_money(shipping_cost, default="0.00"),
            currency=price.get("currency", "USD"),
            condition=_ebay_condition(body.get("condition")),
            listing_status=(
                "ended"
                if body.get("itemEndDate") and body.get("itemSellingStatus") == "ENDED"
                else "active"
            ),
            seller_name=(body.get("seller") or {}).get("username"),
            raw_payload=body,
        )

    def _fetch_bricklink(
        self, listing_id: str, canonical_url: str, settings: ProviderSettings
    ) -> ProviderListing:
        # BrickLink Store API exposes inventory records by inventory ID.
        endpoint = f"https://api.bricklink.com/api/store/v1/inventories/{listing_id}"
        response = requests.get(
            endpoint,
            headers=_bricklink_oauth_header("GET", endpoint, settings),
            timeout=settings.timeout_seconds,
        )
        if response.status_code == 404:
            raise ProviderListingMissingError(
                "BrickLink listing is no longer available"
            )
        if response.status_code >= 400:
            raise ProviderRetrievalError("BrickLink API listing request failed")
        body = response.json()
        data = body.get("data")
        if not isinstance(data, dict):
            raise ProviderRetrievalError("BrickLink API returned an invalid response")
        return ProviderListing(
            marketplace_name="bricklink",
            external_listing_id=listing_id,
            title=(data.get("item") or {}).get("no")
            or f"BrickLink inventory {listing_id}",
            url=canonical_url,
            price=str(data.get("unit_price", "0.00")),
            shipping_price="0.00",
            currency=data.get("currency_code", "USD"),
            condition="new" if data.get("new_or_used") == "N" else "used",
            listing_status="active" if data.get("is_retain") is not False else "ended",
            seller_name=None,
            raw_payload=body,
        )


def _required_text(body: dict[str, Any], key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProviderRetrievalError(f"provider response missing {key}")
    return value


def _money(value: Any, default: str | None = None) -> str:
    if value is None and default is not None:
        return default
    if not isinstance(value, dict) or value.get("value") is None:
        raise ProviderRetrievalError("provider response has invalid price")
    return str(value["value"])


def _ebay_condition(value: Any) -> str:
    return (
        "new"
        if isinstance(value, str) and value.lower().startswith("new")
        else "used" if value else "unknown"
    )


def _bricklink_oauth_header(method: str, url: str, settings: ProviderSettings) -> str:
    """Create the OAuth 1.0 HMAC-SHA1 header required by BrickLink's API."""
    nonce = str(time.time_ns())
    params = {
        "oauth_consumer_key": settings.consumer_key or "",
        "oauth_nonce": nonce,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": settings.token_value or "",
        "oauth_version": "1.0",
    }
    encoded = urlencode(sorted(params.items()), quote_via=quote, safe="~")
    base = "&".join([method.upper(), quote(url, safe="~"), quote(encoded, safe="~")])
    key = f"{quote(settings.consumer_secret or '', safe='~')}&{quote(settings.token_secret or '', safe='~')}"
    params["oauth_signature"] = base64.b64encode(
        hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()
    ).decode()
    return "OAuth " + ", ".join(
        f'{quote(key, safe="~") }="{quote(value, safe="~")}"'
        for key, value in sorted(params.items())
    )
