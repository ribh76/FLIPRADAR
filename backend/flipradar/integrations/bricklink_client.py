"""Live BrickLink catalog and price-guide client (OAuth 1.0 HMAC-SHA1)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qsl, quote, urlsplit

import requests

from flipradar.api.schemas.validation import normalize_set_number
from flipradar.core.settings import get_settings
from flipradar.integrations.marketplace_adapter import MarketplaceAdapter

_BASE_URL = "https://api.bricklink.com/api/store/v1"


class BricklinkApiError(RuntimeError):
    pass


class BricklinkNotFoundError(BricklinkApiError):
    pass


class BricklinkClient:
    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()

    @property
    def configured(self) -> bool:
        return get_settings().marketplace.bricklink.usable

    def get_set_metadata(self, set_number: str) -> dict[str, Any]:
        item = self._get(f"/items/SET/{self._set_id(set_number)}")
        return {
            "set_number": normalize_set_number(set_number),
            "name": item.get("name"),
            "theme": item.get("category_name")
            or f"BrickLink category {item.get('category_id', 'unknown')}",
            "subtheme": item.get("category_name"),
            "release_year": item.get("year_released"),
            "retirement_year": item.get("year_last_produced"),
            "piece_count": item.get("no_of_parts"),
            "minifig_count": item.get("no_of_minifigs"),
        }

    def get_set_price_snapshot(self, set_number: str) -> dict[str, Any]:
        guides = [
            self.get_price_guide("SET", self._set_id(set_number), condition)
            for condition in ("N", "U")
        ]
        usable = [guide for guide in guides if guide]
        if not usable:
            raise BricklinkNotFoundError(
                f"BrickLink price guide not found: {set_number}"
            )
        values = [
            Decimal(str(guide.get("avg_price")))
            for guide in usable
            if guide.get("avg_price") is not None
        ]
        if not values:
            raise BricklinkApiError("BrickLink returned no average price")
        primary = usable[0]
        lows = [
            Decimal(str(guide.get("min_price")))
            for guide in usable
            if guide.get("min_price") is not None
        ]
        highs = [
            Decimal(str(guide.get("max_price")))
            for guide in usable
            if guide.get("max_price") is not None
        ]
        return {
            "condition": "new",
            "currency": primary.get("currency_code", "USD"),
            "low_price": min(lows or values),
            "median_price": values[0],
            "average_price": sum(values) / len(values),
            "high_price": max(highs or values),
            "fair_market_value": sum(values) / len(values),
            "listing_count": sum(int(g.get("unit_quantity") or 0) for g in usable),
        }

    def get_part_catalog_records(self, query: str) -> list[dict[str, Any]]:
        # BrickLink does not expose a general catalog-search endpoint. A provider lookup is exact by part number.
        part_number = query.strip()
        if not part_number:
            return []
        item = self._get(f"/items/PART/{quote(part_number, safe='')}")
        guide = self.get_price_guide("PART", part_number, "N")
        category_id = str(item.get("category_id", "unknown"))
        name = item.get("name") or part_number
        price = guide.get("avg_price") if guide else None
        return [
            {
                "source": {
                    "name": "BrickLink catalog",
                    "url": self._catalog_url("P", part_number),
                },
                "category": {
                    "id": category_id,
                    "name": item.get("category_name")
                    or f"BrickLink category {category_id}",
                },
                "color": {"id": "unknown", "name": "Unspecified"},
                "part": {
                    "part_num": part_number,
                    "name": name,
                    "image_urls": [item["image_url"]] if item.get("image_url") else [],
                    "first_known_year": item.get("year_released"),
                    "market_price": price,
                    "market_price_currency": (guide or {}).get("currency_code", "USD"),
                },
                "element": {
                    "element_id": part_number,
                    "name": name,
                    "first_known_year": item.get("year_released"),
                },
            }
        ]

    def get_price_guide(
        self, item_type: str, number: str, condition: str
    ) -> dict[str, Any] | None:
        try:
            return self._get(
                f"/items/{item_type}/{quote(number, safe='')}/price",
                {
                    "guide_type": "sold",
                    "new_or_used": condition,
                    "currency_code": "USD",
                },
            )
        except BricklinkNotFoundError:
            return None

    def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        settings = get_settings().marketplace.bricklink
        if not settings.usable or not all(
            (
                settings.consumer_key,
                settings.consumer_secret,
                settings.token_value,
                settings.token_secret,
            )
        ):
            raise BricklinkApiError("BrickLink API is not configured")
        url = f"{_BASE_URL}{path}"
        response = self._session.get(
            url,
            params=params,
            headers={
                "Authorization": self._authorization_header(url, params or {}, settings)
            },
            timeout=settings.timeout_seconds,
        )
        if response.status_code == 404:
            raise BricklinkNotFoundError(f"BrickLink resource not found: {path}")
        try:
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise BricklinkApiError(
                f"BrickLink request failed: {response.text[:500]}"
            ) from exc
        if payload.get("meta", {}).get("code") not in (None, 200):
            raise BricklinkApiError(
                str(
                    payload.get("meta", {}).get("message")
                    or "BrickLink API rejected request"
                )
            )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise BricklinkApiError("BrickLink response did not contain an object")
        return data

    @staticmethod
    def _set_id(set_number: str) -> str:
        normalized = normalize_set_number(set_number)
        return normalized if "-" in normalized else f"{normalized}-1"

    @staticmethod
    def _catalog_url(item_type: str, number: str) -> str:
        return f"https://www.bricklink.com/v2/catalog/catalogitem.page?{item_type}={quote(number, safe='')}"

    @staticmethod
    def _authorization_header(url: str, params: dict[str, str], settings: Any) -> str:
        oauth = {
            "oauth_consumer_key": settings.consumer_key,
            "oauth_token": settings.token_value,
            "oauth_nonce": secrets.token_hex(16),
            "oauth_timestamp": str(int(time.time())),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_version": "1.0",
        }
        pieces = urlsplit(url)
        signature_params = (
            list(parse_qsl(pieces.query, keep_blank_values=True))
            + list(params.items())
            + list(oauth.items())
        )
        encoded = sorted(
            (quote(str(k), safe="~"), quote(str(v), safe="~"))
            for k, v in signature_params
        )
        parameter_string = "&".join(f"{k}={v}" for k, v in encoded)
        base_url = f"{pieces.scheme}://{pieces.netloc}{pieces.path}"
        base = "&".join(
            ("GET", quote(base_url, safe="~"), quote(parameter_string, safe="~"))
        )
        key = f"{quote(settings.consumer_secret, safe='~')}&{quote(settings.token_secret, safe='~')}"
        oauth["oauth_signature"] = base64.b64encode(
            hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()
        ).decode()
        return "OAuth " + ", ".join(
            f'{quote(k, safe="~")}="{quote(str(v), safe="~")}"'
            for k, v in sorted(oauth.items())
        )


class BricklinkMarketplaceAdapter(MarketplaceAdapter):
    marketplace = "bricklink"

    def __init__(self, client: BricklinkClient | None = None) -> None:
        self._client = client or BricklinkClient()

    def fetch_listings(self, set_number: str) -> list[dict[str, Any]]:
        listings: list[dict[str, Any]] = []
        set_id = self._client._set_id(set_number)
        for condition in ("N", "U"):
            guide = self._client.get_price_guide("SET", set_id, condition)
            if not guide:
                continue
            for index, detail in enumerate(guide.get("price_detail", [])):
                if not isinstance(detail, dict) or detail.get("unit_price") is None:
                    continue
                listings.append(
                    {
                        "external_listing_id": f"price-guide:{set_id}:{condition}:{index}",
                        "price": detail["unit_price"],
                        "shipping_price": 0,
                        "condition": condition,
                        "title": f"LEGO {normalize_set_number(set_number)}",
                        "listing_url": BricklinkClient._catalog_url("S", set_id),
                        "currency": guide.get("currency_code", "USD"),
                        "source_payload": detail,
                    }
                )
        return self._tag_marketplace(listings)


client = BricklinkClient()
adapter = BricklinkMarketplaceAdapter(client)
