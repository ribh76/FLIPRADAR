"""Live eBay Browse API adapter used for marketplace pricing."""

from __future__ import annotations

import base64
import time
from typing import Any, cast

import requests

from flipradar.api.schemas.validation import normalize_set_number
from flipradar.core.settings import get_settings
from flipradar.integrations.marketplace_adapter import MarketplaceAdapter


class EbayApiError(RuntimeError):
    pass


class EbayMarketplaceAdapter(MarketplaceAdapter):
    marketplace = "ebay"
    _token: str | None = None
    _token_expires_at = 0.0

    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()

    def fetch_listings(self, set_number: str) -> list[dict[str, Any]]:
        settings = get_settings().marketplace.ebay
        if not settings.usable or not settings.api_key or not settings.api_secret:
            raise EbayApiError("eBay API is not configured")
        token = self._application_token(
            settings.api_key, settings.api_secret, settings.timeout_seconds
        )
        response = self._session.get(
            "https://api.ebay.com/buy/browse/v1/item_summary/search",
            params={"q": f"LEGO {normalize_set_number(set_number)}", "limit": 50},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            },
            timeout=settings.timeout_seconds,
        )
        self._raise_for_status(response, "search listings")
        payload = response.json()
        return self._tag_marketplace(
            [
                self._listing(item)
                for item in payload.get("itemSummaries", [])
                if isinstance(item, dict)
            ]
        )

    def _application_token(self, key: str, secret: str, timeout: int) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        basic = base64.b64encode(f"{key}:{secret}".encode()).decode()
        response = self._session.post(
            "https://api.ebay.com/identity/v1/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=timeout,
        )
        self._raise_for_status(response, "obtain application token")
        payload = response.json()
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise EbayApiError("eBay OAuth response did not contain an access token")
        self._token = token
        self._token_expires_at = time.monotonic() + max(
            int(payload.get("expires_in", 7200)) - 60, 0
        )
        return token

    @staticmethod
    def _listing(item: dict[str, Any]) -> dict[str, Any]:
        price = (
            cast(dict[str, Any], item.get("price"))
            if isinstance(item.get("price"), dict)
            else {}
        )
        shipping = (
            cast(list[dict[str, Any]], item.get("shippingOptions"))
            if isinstance(item.get("shippingOptions"), list)
            else []
        )
        shipping_cost = next(
            (
                cast(dict[str, Any], option.get("shippingCost")).get("value")
                for option in shipping
                if isinstance(option, dict)
                and isinstance(option.get("shippingCost"), dict)
            ),
            0,
        )
        seller = (
            cast(dict[str, Any], item.get("seller"))
            if isinstance(item.get("seller"), dict)
            else {}
        )
        return {
            "external_listing_id": item.get("itemId"),
            "price": price.get("value"),
            "shipping_price": shipping_cost,
            "condition": item.get("condition"),
            "title": item.get("title"),
            "listing_url": item.get("itemWebUrl") or item.get("itemHref"),
            "seller": seller.get("username") or seller.get("feedbackScore"),
            "currency": price.get("currency"),
            "source_payload": item,
        }

    @staticmethod
    def _raise_for_status(response: requests.Response, operation: str) -> None:
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            raise EbayApiError(
                f"eBay failed to {operation}: {response.text[:500]}"
            ) from exc


adapter = EbayMarketplaceAdapter()
