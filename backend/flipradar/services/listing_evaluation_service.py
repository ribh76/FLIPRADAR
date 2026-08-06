"""Safe, API-first ingestion of an individual marketplace listing."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.schemas.listing_schema import ListingEvaluationRequest
from flipradar.core.settings import get_settings
from flipradar.database import repositories
from flipradar.domain.models import MarketplaceListing
from flipradar.integrations.listing_provider_client import (
    OfficialListingProviderClient,
    ProviderListingMissingError,
    ProviderRetrievalError,
    ProviderTimeoutError,
)
from flipradar.services.errors import (
    ServiceNotFoundError,
    ServiceProviderError,
    ServiceProviderTimeoutError,
)
from flipradar.services.listing_url_ingestion import (
    CanonicalListingUrl,
    normalize_listing_url,
    resolve_shortened_url,
)

RECENT_EVALUATION_WINDOW = timedelta(minutes=5)
PROVIDER_REQUEST_SPACING_SECONDS = 0.25
_provider_lock = asyncio.Lock()
_provider_last_request: dict[str, datetime] = {}
provider_client = OfficialListingProviderClient()


async def evaluate_listing_url(
    db: AsyncSession, payload: ListingEvaluationRequest
) -> MarketplaceListing:
    target = normalize_listing_url(payload.url)
    settings = get_settings().marketplace
    provider_settings = getattr(settings, target.provider)
    if target.is_shortened:
        target = await asyncio.to_thread(
            resolve_shortened_url,
            target.url,
            timeout_seconds=provider_settings.timeout_seconds,
        )
    lego_set = await repositories.get_set_by_number(db, payload.set_number)
    if lego_set is None:
        raise ServiceNotFoundError("LEGO set not found")
    marketplace = await repositories.get_or_create_marketplace(db, target.provider)
    existing = await repositories.get_existing_listing(
        db, marketplace.id, target.external_listing_id
    )
    existing_seen_at = (
        existing.last_seen_at.replace(tzinfo=UTC)
        if existing and existing.last_seen_at.tzinfo is None
        else (existing.last_seen_at if existing else None)
    )
    if (
        existing_seen_at
        and existing_seen_at >= datetime.now(UTC) - RECENT_EVALUATION_WINDOW
    ):
        return existing
    try:
        provider_listing = await _fetch_provider(target, provider_settings)
        data = _provider_data(provider_listing, target)
    except ProviderListingMissingError as exc:
        if existing is not None:
            return await repositories.update_listing(
                db, existing, {"listing_status": "removed", "is_verified": True}
            )
        if payload.manual_listing is None:
            raise ServiceNotFoundError(
                "Listing has been removed by the provider"
            ) from exc
        data = _manual_data(payload, target)
    except ProviderTimeoutError as exc:
        if payload.manual_listing is None:
            raise ServiceProviderTimeoutError(str(exc)) from exc
        data = _manual_data(payload, target)
    except (ProviderRetrievalError, TimeoutError) as exc:
        if payload.manual_listing is None:
            if isinstance(exc, TimeoutError):
                raise ServiceProviderTimeoutError(
                    f"{target.provider} API timed out"
                ) from exc
            raise ServiceProviderError(str(exc)) from exc
        data = _manual_data(payload, target)
    if existing is not None:
        return await repositories.update_listing(db, existing, data)
    return await repositories.create_listing(
        db, lego_set_id=lego_set.id, marketplace_id=marketplace.id, listing_data=data
    )


async def _fetch_provider(target: CanonicalListingUrl, provider_settings):
    async with _provider_lock:
        now = datetime.now(UTC)
        wait = (
            PROVIDER_REQUEST_SPACING_SECONDS
            - (
                now
                - _provider_last_request.get(
                    target.provider, datetime.min.replace(tzinfo=UTC)
                )
            ).total_seconds()
        )
        if wait > 0:
            await asyncio.sleep(wait)
        _provider_last_request[target.provider] = datetime.now(UTC)
    return await asyncio.wait_for(
        asyncio.to_thread(
            provider_client.fetch,
            target.provider,
            target.external_listing_id,
            target.url,
            provider_settings,
        ),
        timeout=provider_settings.timeout_seconds,
    )


def _provider_data(item, target: CanonicalListingUrl) -> dict:
    try:
        price = Decimal(item.price)
        shipping = Decimal(item.shipping_price)
    except Exception as exc:
        raise ProviderRetrievalError("provider response has invalid pricing") from exc
    if (
        not item.title.strip()
        or len(item.title) > 500
        or not price.is_finite()
        or not shipping.is_finite()
        or price < 0
        or shipping < 0
        or len(item.currency) != 3
        or not item.currency.isalpha()
        or item.condition not in {"new", "used", "unknown"}
        or item.listing_status not in {"active", "sold", "ended", "removed"}
    ):
        raise ProviderRetrievalError("provider response contains invalid listing data")
    return {
        "external_listing_id": item.external_listing_id,
        "title": item.title,
        # Provider API URLs are data only; persist our allowlisted canonical URL.
        "url": target.url,
        "price": price,
        "shipping_price": shipping,
        "total_price": price + shipping,
        "currency": item.currency.upper(),
        "condition": item.condition,
        "listing_status": item.listing_status,
        "seller_name": item.seller_name,
        "is_complete": item.is_complete,
        "is_sealed": item.is_sealed,
        "raw_payload": item.raw_payload,
        "is_verified": True,
    }


def _manual_data(
    payload: ListingEvaluationRequest, target: CanonicalListingUrl
) -> dict:
    manual = payload.manual_listing
    assert manual is not None
    return {
        "external_listing_id": target.external_listing_id,
        "title": manual.title,
        "url": target.url,
        "price": manual.price,
        "shipping_price": manual.shipping_price,
        "total_price": manual.price + manual.shipping_price,
        "currency": manual.currency,
        "condition": manual.condition,
        "listing_status": manual.listing_status,
        "seller_name": manual.seller_name,
        "is_complete": manual.is_complete,
        "is_sealed": manual.is_sealed,
        "raw_payload": {"source": "manual_fallback", "original_url": payload.url},
        "is_verified": False,
    }
