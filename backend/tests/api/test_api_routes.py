import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import flipradar.domain.models  # noqa: F401
from flipradar.core.settings import get_settings
from flipradar.database import Base, get_db_session, repositories
from flipradar.domain.engines import price_estimator
from flipradar.domain.models import User
from flipradar.integrations import bricklink_mock_client
from flipradar.integrations.listing_provider_client import (
    ProviderListing,
    ProviderRetrievalError,
)
from flipradar.main import create_app
from flipradar.services import (
    auth_service,
    listing_evaluation_service,
    marketplace_service,
    portfolio_service,
    recommendation_service,
)
from flipradar.services.errors import ServiceProviderError, ServiceProviderTimeoutError

logger = logging.getLogger(__name__)
VALID_PASSWORD = "Str0ng!Pass"


@pytest.fixture
def client():
    app = create_app()
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async def create_schema():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def drop_schema():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    import asyncio

    asyncio.run(create_schema())
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def override_get_db_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_get_db_session
    logger.info("test database setup complete")

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    asyncio.run(drop_schema())
    logger.info("test database cleanup complete")


def random_set_number() -> str:
    return str(int(uuid4().int % 900000) + 100000)


def create_set_payload(set_number: str | None = None) -> dict:
    resolved_set_number = set_number or random_set_number()
    return {
        "set_number": resolved_set_number,
        "name": f"API Test Set {resolved_set_number}",
        "theme": "Icons",
        "subtheme": "Pytest",
        "release_year": 2024,
        "retirement_year": 2026,
        "piece_count": 1250,
        "minifig_count": 4,
    }


def create_lego_set(client: TestClient, set_number: str | None = None) -> dict:
    payload = create_set_payload(set_number)
    response = client.post("/sets", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def create_listing_payload(set_number: str) -> dict:
    price = Decimal("149.99")
    shipping = Decimal("12.50")
    return {
        "set_number": set_number,
        "marketplace_name": "ebay",
        "external_listing_id": f"listing-{uuid4().hex}",
        "title": f"LEGO {set_number} sealed complete set",
        "url": "https://www.ebay.com/itm/test-listing",
        "price": str(price),
        "shipping_price": str(shipping),
        "total_price": str(price + shipping),
        "currency": "USD",
        "condition": "new",
        "listing_status": "active",
        "seller_name": "api-test-seller",
        "seller_rating": "99.50",
        "is_complete": True,
        "is_sealed": True,
        "match_confidence": "98.25",
        "match_reasons": ["exact_set_number"],
        "exclusion_flags": [],
        "raw_payload": {"source": "pytest-api"},
    }


def create_snapshot_payload(set_number: str, fair_value: str = "152.00") -> dict:
    fair_value_decimal = Decimal(fair_value)
    low_price = max(
        Decimal("0.00"), min(Decimal("120.00"), fair_value_decimal - Decimal("32.00"))
    )
    high_price = max(Decimal("1000.00"), fair_value_decimal + Decimal("38.00"))
    return {
        "set_number": set_number,
        "marketplace_name": "ebay",
        "condition": "new",
        "currency": "USD",
        "low_price": str(low_price),
        "median_price": "150.00",
        "average_price": "151.25",
        "high_price": str(high_price),
        "fair_market_value": fair_value,
        "listing_count": 12,
        "source_payload": {"source": "pytest-api"},
    }


def collection_data(response: Any) -> list:
    body = response.json()
    assert "data" in body
    assert "pagination" in body
    assert body["pagination"]["count"] == len(body["data"])
    return body["data"]


def test_health_endpoint(client: TestClient):
    response = client.get("/health")

    logger.info(f"API TEST: GET /health status={response.status_code}")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_db_health_endpoint(client: TestClient):
    response = client.get("/db-health")

    logger.info(f"API TEST: GET /db-health status={response.status_code}")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"


def test_liveness_and_readiness_endpoints(client: TestClient):
    live_response = client.get("/health/live")
    ready_response = client.get("/health/ready")

    assert live_response.status_code == 200
    assert live_response.json()["status"] == "ok"
    assert ready_response.status_code == 200
    assert ready_response.json()["service"] == "ready"


def test_create_set_endpoint(client: TestClient):
    payload = create_set_payload()
    response = client.post("/sets", json=payload)

    logger.info(f"API TEST: POST /sets status={response.status_code}")
    assert response.status_code == 201
    assert response.json()["set_number"] == payload["set_number"]


def test_create_set_persists_catalog_metadata(client: TestClient):
    payload = create_set_payload()
    payload.update(
        {
            "msrp": "229.99",
            "original_currency": "usd",
            "region": "us",
            "image_urls": [
                "https://images.example.test/primary.jpg",
                "https://images.example.test/alternate.jpg",
            ],
            "source_name": "LEGO Shop",
            "source_url": "https://www.lego.com/en-us/product/test-set",
        }
    )

    response = client.post("/sets", json=payload)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["msrp"] == "229.99"
    assert body["original_currency"] == "USD"
    assert body["region"] == "US"
    assert body["image_urls"] == payload["image_urls"]
    assert body["source_name"] == payload["source_name"]
    assert body["source_url"] == payload["source_url"]


def test_get_set_endpoint(client: TestClient):
    lego_set = create_lego_set(client)
    response = client.get(f"/set/{lego_set['set_number']}")

    logger.info(f"API TEST: GET /set/{{set_number}} status={response.status_code}")
    assert response.status_code == 200
    assert response.json()["set_number"] == lego_set["set_number"]
    assert response.json()["valuation_status"] == "missing_market_data"


def test_get_set_endpoint_returns_bricklink_mock_detail(client: TestClient):
    response = client.get("/set/75192")

    logger.info(
        f"API TEST: GET /set/{{set_number}} BrickLink mock status={response.status_code}"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["set_number"] == "75192"
    assert body["metadata"]["name"] == "Millennium Falcon"
    assert body["latest_snapshot"]["listing_count"] == 18
    assert body["fair_value"] == "725.00"
    assert body["market_low"] == "610.00"
    assert body["market_high"] == "880.00"
    assert body["listing_count"] == 18
    assert body["valuation_status"] == "valued"


def test_get_set_endpoint_with_snapshot_does_not_crash(client: TestClient):
    lego_set = create_lego_set(client)
    snapshot = client.post(
        "/snapshots", json=create_snapshot_payload(lego_set["set_number"])
    ).json()
    response = client.get(f"/set/{lego_set['set_number']}")

    logger.info(
        f"API TEST: GET /set/{{set_number}} with snapshot status={response.status_code}"
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["latest_snapshot"]["id"] == snapshot["id"]
    assert body["valuation_status"] == "valued"
    assert body["listing_count"] == snapshot["listing_count"]


def test_get_set_endpoint_missing_set_returns_404(client: TestClient):
    response = client.get("/set/not-a-mock-set")

    logger.info(
        f"API TEST: GET /set/{{set_number}} missing status={response.status_code}"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "LEGO set not found"
    assert response.json()["error"]["code"] == "not_found"


def test_list_sets_endpoint(client: TestClient):
    lego_set = create_lego_set(client)
    response = client.get("/sets")

    logger.info(f"API TEST: GET /sets status={response.status_code}")
    assert response.status_code == 200
    assert any(
        item["set_number"] == lego_set["set_number"]
        for item in collection_data(response)
    )


def test_list_sets_endpoint_supports_pagination_filtering_and_ordering(
    client: TestClient,
):
    create_lego_set(client, "100001")
    create_lego_set(client, "100002")
    create_lego_set(client, "200001")

    response = client.get(
        "/sets",
        params={
            "limit": 1,
            "offset": 1,
            "query": "100",
            "order": "set_number",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"] == {
        "limit": 1,
        "offset": 1,
        "count": 1,
        "has_more": False,
    }
    assert body["data"][0]["set_number"] == "100002"


def test_marketplace_update_returns_provider_error_response(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    lego_set = create_lego_set(client)

    async def raise_provider_error(*args, **kwargs):
        del args, kwargs
        raise ServiceProviderError("eBay failed after retries")

    monkeypatch.setattr(
        marketplace_service, "_fetch_adapter_listings", raise_provider_error
    )
    response = client.post(f"/marketplace/update/{lego_set['set_number']}")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_error"


def test_marketplace_update_returns_provider_timeout_response(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    lego_set = create_lego_set(client)

    async def raise_provider_timeout(*args, **kwargs):
        del args, kwargs
        raise ServiceProviderTimeoutError("BrickLink timed out after retries")

    monkeypatch.setattr(
        marketplace_service, "_fetch_adapter_listings", raise_provider_timeout
    )
    response = client.post(f"/marketplace/update/{lego_set['set_number']}")

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "provider_timeout"


def test_set_search_supports_partial_local_lookup_and_provider_hydration(
    client: TestClient,
):
    create_lego_set(client, "42071")

    local_response = client.get("/sets/search", params={"query": "420"})
    assert local_response.status_code == 200
    local_body = local_response.json()
    assert local_body["source"] == "local"
    assert local_body["exact_match"] is False
    assert [item["set_number"] for item in local_body["results"]] == ["42071"]

    provider_response = client.get("/sets/search", params={"query": "75192"})
    assert provider_response.status_code == 200
    provider_body = provider_response.json()
    assert provider_body["source"] == "provider"
    assert provider_body["exact_match"] is True
    assert isinstance(provider_body["results"], list)
    assert provider_body["results"][0]["name"] == "Millennium Falcon"
    assert provider_body["results"][0]["source_name"] == "Bricklink catalog"

    cached_response = client.get("/sets/search", params={"query": "75192"})
    assert cached_response.status_code == 200
    assert cached_response.json()["source"] == "local"


def test_set_search_returns_not_found_and_incomplete_provider_errors(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    not_found = client.get("/sets/search", params={"query": "99999"})
    assert not_found.status_code == 404
    assert "not found" in not_found.json()["error"]["message"].lower()

    monkeypatch.setattr(
        bricklink_mock_client,
        "fetch_set_metadata",
        lambda set_number: {"set_number": set_number, "name": "Incomplete"},
    )
    incomplete = client.get("/sets/search", params={"query": "99999"})
    assert incomplete.status_code == 422
    assert "incomplete" in incomplete.json()["error"]["message"].lower()


def test_create_listing_endpoint(client: TestClient):
    lego_set = create_lego_set(client)
    payload = create_listing_payload(lego_set["set_number"])
    response = client.post("/listings", json=payload)

    logger.info(f"API TEST: POST /listings status={response.status_code}")
    assert response.status_code == 201
    assert response.json()["external_listing_id"] == payload["external_listing_id"]


def test_listing_evaluation_uses_provider_data_and_deduplicates_recent_requests(
    client: TestClient, monkeypatch
):
    lego_set = create_lego_set(client)
    calls = []

    def fetch(provider, listing_id, url, settings):
        calls.append((provider, listing_id, url))
        return ProviderListing(
            marketplace_name="ebay",
            external_listing_id=listing_id,
            title="Verified LEGO listing",
            url=url,
            price="100.00",
            shipping_price="10.00",
            currency="USD",
            condition="new",
            raw_payload={"itemId": listing_id},
        )

    monkeypatch.setattr(listing_evaluation_service.provider_client, "fetch", fetch)
    payload = {
        "set_number": lego_set["set_number"],
        "url": "https://m.ebay.com/itm/123456789012?campid=x",
    }
    first = client.post("/listing-evaluations", json=payload)
    second = client.post("/listing-evaluations", json=payload)

    assert first.status_code == 201, first.text
    assert first.json()["is_verified"] is True
    assert second.status_code == 201
    assert len(calls) == 1


def test_listing_evaluation_allows_manual_fallback_when_provider_fails(
    client: TestClient, monkeypatch
):
    lego_set = create_lego_set(client)

    def fail(*args, **kwargs):
        raise ProviderRetrievalError("provider unavailable")

    monkeypatch.setattr(listing_evaluation_service.provider_client, "fetch", fail)
    response = client.post(
        "/listing-evaluations",
        json={
            "set_number": lego_set["set_number"],
            "url": "https://www.ebay.com/itm/123456789013",
            "manual_listing": {
                "title": "Manual LEGO listing",
                "price": "75.00",
                "shipping_price": "5.00",
                "currency": "USD",
            },
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["is_verified"] is False
    assert response.json()["total_price"] == "80.00"


def test_listing_evaluation_rejects_private_and_unsupported_urls(client: TestClient):
    lego_set = create_lego_set(client)
    for url in (
        "https://127.0.0.1/itm/123456789012",
        "https://evil.test/itm/123456789012",
    ):
        response = client.post(
            "/listing-evaluations",
            json={"set_number": lego_set["set_number"], "url": url},
        )
        assert response.status_code == 400


def test_listing_analysis_persists_scored_decision_and_risks(
    client: TestClient, monkeypatch
):
    lego_set = create_lego_set(client, "75192")
    listing_payload = create_listing_payload(lego_set["set_number"])
    listing_payload.update(
        {
            "title": "LEGO 75192 sealed complete set",
            "price": "500.00",
            "shipping_price": "20.00",
            "total_price": "520.00",
            "seller_rating": "99.00",
            "is_verified": True,
        }
    )
    listing = client.post("/listings", json=listing_payload).json()

    class Snapshot:
        metric_type = "fair_market_value"
        currency = "USD"
        condition = "new"
        value = Decimal("725.00")
        sample_size = 12
        retrieval_time = datetime.now(UTC)

    class LowSnapshot(Snapshot):
        metric_type = "low"
        value = Decimal("680.00")

    class HighSnapshot(Snapshot):
        metric_type = "high"
        value = Decimal("760.00")

    async def snapshots(*args, **kwargs):
        return {lego_set["set_number"]: [Snapshot(), LowSnapshot(), HighSnapshot()]}

    monkeypatch.setattr(repositories, "get_latest_snapshots_for_set_numbers", snapshots)
    response = client.post(f"/listings/{listing['id']}/analysis")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["decision"] == "buy"
    assert body["total_cost"] == "520.00"
    assert body["discount_percent"] == "28.30"
    assert body["fair_value_low"] == "680.00"
    assert body["fair_value_high"] == "760.00"
    assert body["product_match_confidence"] == "100.00"
    assert body["valuation_sample_size"] == 12
    assert body["reasons"]


def test_listing_analysis_returns_insufficient_data_without_fair_value(
    client: TestClient,
):
    lego_set = create_lego_set(client)
    listing = client.post(
        "/listings", json=create_listing_payload(lego_set["set_number"])
    ).json()
    response = client.post(f"/listings/{listing['id']}/analysis")
    assert response.status_code == 201, response.text
    assert response.json()["decision"] == "insufficient_data"
    assert "missing_fair_value" in response.json()["risk_flags"]


def test_deals_endpoint_returns_ranked_metrics_and_marketplace_details(
    client: TestClient,
):
    lego_set = create_lego_set(client, "75313")
    listing = create_listing_payload(lego_set["set_number"])
    listing.update(
        {
            "detected_set_number": lego_set["set_number"],
            "price": "500.00",
            "shipping_price": "20.00",
            "total_price": "520.00",
        }
    )
    assert client.post("/listings", json=listing).status_code == 201
    snapshot = {
        "set_number": lego_set["set_number"],
        "marketplace_name": "ebay",
        "condition": "new",
        "currency": "USD",
        "metric_type": "fair_market_value",
        "value": "725.00",
        "sample_size": 12,
    }
    assert client.post("/snapshots", json=snapshot).status_code == 201

    response = client.get("/deals")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pagination"]["count"] == 1
    deal = body["data"][0]
    assert deal["value"] == "725.00"
    assert deal["discount"] == "28.3"
    assert deal["score"] > 0
    assert deal["confidence"] > 0
    assert deal["marketplace"]["name"] == "ebay"
    assert deal["marketplace"]["seller_name"] == "api-test-seller"
    assert body["refresh"]["cached"] is False


def test_deals_endpoint_rejects_invalid_filter_ranges(client: TestClient):
    response = client.get("/deals", params={"min_budget": 200, "max_budget": 100})

    assert response.status_code == 422
    assert response.json()["detail"] == "minimum budget cannot exceed maximum budget"


def test_duplicate_listing_returns_conflict(client: TestClient):
    lego_set = create_lego_set(client)
    payload = create_listing_payload(lego_set["set_number"])
    assert client.post("/listings", json=payload).status_code == 201

    response = client.post("/listings", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "Marketplace listing already exists"
    assert response.json()["error"]["code"] == "conflict"


def test_listings_by_set_endpoint(client: TestClient):
    lego_set = create_lego_set(client)
    listing = client.post(
        "/listings", json=create_listing_payload(lego_set["set_number"])
    ).json()
    response = client.get(f"/listings/{lego_set['set_number']}")

    logger.info(f"API TEST: GET /listings/{{set_number}} status={response.status_code}")
    assert response.status_code == 200
    saved_listing = next(
        item for item in collection_data(response) if item["id"] == listing["id"]
    )
    assert saved_listing["match_reasons"] == ["exact_set_number"]
    assert saved_listing["exclusion_flags"] == []


def test_listings_by_set_endpoint_supports_pagination_and_filters(
    client: TestClient,
):
    lego_set = create_lego_set(client)
    new_listing = create_listing_payload(lego_set["set_number"])
    used_listing = create_listing_payload(lego_set["set_number"])
    used_listing.update({"condition": "used"})
    assert client.post("/listings", json=new_listing).status_code == 201
    assert client.post("/listings", json=used_listing).status_code == 201

    response = client.get(
        f"/listings/{lego_set['set_number']}",
        params={"condition": "used", "limit": 1, "offset": 0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["count"] == 1
    assert body["data"][0]["condition"] == "used"


def test_listings_by_exact_sets_set_number_endpoint(client: TestClient):
    lego_set = create_lego_set(client)
    response = client.get(f"/sets/{lego_set['set_number']}")

    logger.info(f"API TEST: GET /sets/{{set_number}} status={response.status_code}")
    assert response.status_code == 200
    assert response.json()["set_number"] == lego_set["set_number"]
    assert response.json()["latest_snapshot"] is None


def test_listings_by_sets_set_number_listings_endpoint(client: TestClient):
    lego_set = create_lego_set(client)
    listing = client.post(
        "/listings", json=create_listing_payload(lego_set["set_number"])
    ).json()
    response = client.get(f"/sets/{lego_set['set_number']}/listings")

    logger.info(
        f"API TEST: GET /sets/{{set_number}}/listings status={response.status_code}"
    )
    assert response.status_code == 200
    assert any(item["id"] == listing["id"] for item in collection_data(response))


def test_latest_listing_endpoint(client: TestClient):
    lego_set = create_lego_set(client)
    listing = client.post(
        "/listings", json=create_listing_payload(lego_set["set_number"])
    ).json()
    response = client.get(f"/listings/{lego_set['set_number']}/latest")

    logger.info(
        f"API TEST: GET /listings/{{set_number}}/latest status={response.status_code}"
    )
    assert response.status_code == 200
    assert response.json()["id"] == listing["id"]


def test_create_snapshot_endpoint(client: TestClient):
    lego_set = create_lego_set(client)
    payload = create_snapshot_payload(lego_set["set_number"])
    response = client.post("/snapshots", json=payload)

    logger.info(f"API TEST: POST /snapshots status={response.status_code}")
    assert response.status_code == 201
    assert response.json()["fair_market_value"] == payload["fair_market_value"]


def test_duplicate_snapshot_returns_conflict(client: TestClient):
    lego_set = create_lego_set(client)
    payload = create_snapshot_payload(lego_set["set_number"])
    payload["snapshot_at"] = datetime.now(UTC).isoformat()
    assert client.post("/snapshots", json=payload).status_code == 201

    response = client.post("/snapshots", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "Price snapshot already exists"
    assert response.json()["error"]["code"] == "conflict"


def test_snapshots_by_set_endpoint(client: TestClient):
    lego_set = create_lego_set(client)
    snapshot = client.post(
        "/snapshots", json=create_snapshot_payload(lego_set["set_number"])
    ).json()
    response = client.get(f"/snapshots/{lego_set['set_number']}")

    logger.info(
        f"API TEST: GET /snapshots/{{set_number}} status={response.status_code}"
    )
    assert response.status_code == 200
    assert any(item["id"] == snapshot["id"] for item in collection_data(response))


def test_snapshots_by_set_endpoint_supports_pagination_and_filters(
    client: TestClient,
):
    lego_set = create_lego_set(client)
    new_snapshot = create_snapshot_payload(lego_set["set_number"])
    used_snapshot = create_snapshot_payload(lego_set["set_number"], fair_value="99.00")
    used_snapshot.update({"marketplace_name": "bricklink", "condition": "used"})
    assert client.post("/snapshots", json=new_snapshot).status_code == 201
    assert client.post("/snapshots", json=used_snapshot).status_code == 201

    response = client.get(
        f"/snapshots/{lego_set['set_number']}",
        params={"condition": "used", "marketplace_name": "bricklink", "limit": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["count"] == 1
    assert body["data"][0]["condition"] == "used"


def test_latest_snapshot_endpoint(client: TestClient):
    lego_set = create_lego_set(client)
    snapshot = client.post(
        "/snapshots", json=create_snapshot_payload(lego_set["set_number"])
    ).json()
    response = client.get(f"/snapshots/{lego_set['set_number']}/latest")

    logger.info(
        f"API TEST: GET /snapshots/{{set_number}}/latest status={response.status_code}"
    )
    assert response.status_code == 200
    assert response.json()["id"] == snapshot["id"]


def test_set_number_marketplace_and_condition_values_are_normalized(
    client: TestClient,
):
    set_response = client.post("/sets", json=create_set_payload("  abc123-1 "))
    assert set_response.status_code == 201, set_response.text
    assert set_response.json()["set_number"] == "ABC123-1"

    listing_payload = create_listing_payload(" abc123-1 ")
    listing_payload.update({"marketplace_name": " EBAY ", "condition": "New"})
    listing_response = client.post("/listings", json=listing_payload)
    assert listing_response.status_code == 201, listing_response.text
    assert listing_response.json()["condition"] == "new"

    snapshot_payload = create_snapshot_payload(" abc123-1 ")
    snapshot_payload.update({"marketplace_name": " BRICKLINK ", "condition": "Used"})
    snapshot_response = client.post("/snapshots", json=snapshot_payload)
    assert snapshot_response.status_code == 201, snapshot_response.text
    assert snapshot_response.json()["condition"] == "used"

    detail_response = client.get("/sets/abc123-1")
    assert detail_response.status_code == 200
    assert detail_response.json()["set_number"] == "ABC123-1"


def test_listing_validation_rejects_bad_money_marketplace_and_condition(
    client: TestClient,
):
    lego_set = create_lego_set(client)
    payload = create_listing_payload(lego_set["set_number"])

    bad_price = {**payload, "price": "-1.00"}
    assert client.post("/listings", json=bad_price).status_code == 422

    bad_scale = {**payload, "price": "149.999"}
    assert client.post("/listings", json=bad_scale).status_code == 422

    bad_total = {**payload, "total_price": "999.00"}
    assert client.post("/listings", json=bad_total).status_code == 422

    bad_marketplace = {**payload, "marketplace_name": "amazon"}
    assert client.post("/listings", json=bad_marketplace).status_code == 422

    bad_condition = {**payload, "condition": "sealed"}
    assert client.post("/listings", json=bad_condition).status_code == 422


def test_snapshot_validation_rejects_bad_values_and_marketplace(
    client: TestClient,
):
    lego_set = create_lego_set(client)
    payload = create_snapshot_payload(lego_set["set_number"])

    bad_range = {**payload, "low_price": "200.00", "high_price": "100.00"}
    assert client.post("/snapshots", json=bad_range).status_code == 422

    bad_median = {**payload, "median_price": "2000.00"}
    assert client.post("/snapshots", json=bad_median).status_code == 422

    bad_scale = {**payload, "fair_market_value": "152.999"}
    assert client.post("/snapshots", json=bad_scale).status_code == 422

    bad_marketplace = {**payload, "marketplace_name": "amazon"}
    assert client.post("/snapshots", json=bad_marketplace).status_code == 422


def test_portfolio_validation_rejects_bad_quantity_money_and_condition(
    client: TestClient,
):
    lego_set = create_lego_set(client)
    headers = auth_headers(client, "validation-portfolio-user")
    payload = {
        "set_number": lego_set["set_number"],
        "quantity": 1,
        "purchase_price": "100.00",
        "condition": "used",
    }

    bad_quantity = {**payload, "quantity": 0}
    assert (
        client.post("/portfolio/items", headers=headers, json=bad_quantity).status_code
        == 422
    )

    bad_money = {**payload, "purchase_price": "100.999"}
    assert (
        client.post("/portfolio/items", headers=headers, json=bad_money).status_code
        == 422
    )

    bad_condition = {**payload, "condition": "damaged"}
    assert (
        client.post("/portfolio/items", headers=headers, json=bad_condition).status_code
        == 422
    )


def auth_headers(client: TestClient, username: str | None = None) -> dict:
    resolved_username = username or f"user-{uuid4().hex[:8]}"
    response = client.post(
        "/auth/register",
        json={
            "username": resolved_username,
            "email": f"{resolved_username}@example.com",
            "password": VALID_PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def bearer_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def test_saved_search_crud_limit_validation_and_ownership(client: TestClient):
    owner_headers = auth_headers(client, "saved-search-owner")
    other_headers = auth_headers(client, "saved-search-other")
    payload = {
        "name": "Retired Star Wars",
        "filter_config": {"theme": "Star Wars", "retirement_status": "retired"},
    }
    created = client.post("/saved-searches", headers=owner_headers, json=payload)
    assert created.status_code == 201, created.text
    search = created.json()

    listed = client.get("/saved-searches", headers=owner_headers)
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == payload["name"]
    assert (
        client.patch(
            f"/saved-searches/{search['id']}",
            headers=owner_headers,
            json={"name": "Retired UCS", "filter_config": {"min_discount": 20}},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/saved-searches/{search['id']}/duplicate", headers=owner_headers
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/saved-searches/{search['id']}/run",
            headers=owner_headers,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/saved-searches/{search['id']}",
            headers=other_headers,
            json={"name": "not allowed"},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/saved-searches/{search['id']}", headers=owner_headers
        ).status_code
        == 204
    )


def test_watchlist_crud_supports_set_and_listing_entries_with_ownership(
    client: TestClient,
):
    owner_headers = auth_headers(client, "watchlist-owner")
    other_headers = auth_headers(client, "watchlist-other")
    lego_set = create_lego_set(client)

    set_entry = client.post(
        "/watchlist",
        headers=owner_headers,
        json={
            "set_number": lego_set["set_number"],
            "target_price": "125.00",
            "notes": "Wait for a sale",
        },
    )
    assert set_entry.status_code == 201, set_entry.text
    set_item = set_entry.json()
    assert set_item["entry_type"] == "set"
    assert set_item["set_number"] == lego_set["set_number"]
    assert set_item["listing_id"] is None
    assert set_item["last_known_listing_price"] is None
    assert set_item["last_known_listing_status"] is None

    duplicate = client.post(
        "/watchlist",
        headers=owner_headers,
        json={"set_number": lego_set["set_number"]},
    )
    assert duplicate.status_code == 409
    assert (
        client.post(
            "/watchlist",
            headers=other_headers,
            json={"set_number": lego_set["set_number"]},
        ).status_code
        == 201
    )
    assert (
        client.get(f"/watchlist/{set_item['id']}", headers=other_headers).status_code
        == 404
    )

    updated = client.patch(
        f"/watchlist/{set_item['id']}",
        headers=owner_headers,
        json={"target_price": "110.00", "notes": "Only complete sets"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["target_price"] == "110.00"
    assert updated.json()["notes"] == "Only complete sets"

    listing = client.post(
        "/listings", json=create_listing_payload(lego_set["set_number"])
    )
    assert listing.status_code == 201, listing.text
    listing_entry = client.post(
        "/watchlist",
        headers=owner_headers,
        json={"listing_id": listing.json()["id"]},
    )
    assert listing_entry.status_code == 201, listing_entry.text
    listing_item = listing_entry.json()
    assert listing_item["entry_type"] == "listing"
    assert listing_item["last_known_listing_price"] == "162.49"
    assert listing_item["last_known_listing_status"] == "active"
    assert (
        client.post(
            "/watchlist",
            headers=owner_headers,
            json={"listing_id": listing.json()["id"]},
        ).status_code
        == 409
    )

    listed = client.get("/watchlist", headers=owner_headers)
    assert listed.status_code == 200, listed.text
    assert {item["id"] for item in listed.json()} == {
        set_item["id"],
        listing_item["id"],
    }
    assert (
        client.delete(f"/watchlist/{set_item['id']}", headers=owner_headers).status_code
        == 204
    )


def verification_token_from_url(verification_url: str) -> str:
    parsed = urlparse(verification_url)
    tokens = parse_qs(parsed.query).get("token")
    assert tokens, verification_url
    return tokens[0]


def reset_token_from_url(reset_url: str) -> str:
    parsed = urlparse(reset_url)
    tokens = parse_qs(parsed.query).get("token")
    assert tokens, reset_url
    return tokens[0]


def email_change_token_from_url(confirmation_url: str) -> str:
    parsed = urlparse(confirmation_url)
    tokens = parse_qs(parsed.query).get("token")
    assert tokens, confirmation_url
    return tokens[0]


def test_register_success(client: TestClient):
    response = client.post(
        "/auth/register",
        json={
            "username": "collector",
            "email": "collector@example.com",
            "password": VALID_PASSWORD,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["username"] == "collector"
    assert body["user"]["display_name"] == "collector"
    assert body["user"]["is_email_verified"] is False
    assert "hashed_password" not in body
    assert "hashed_password" not in body["user"]

    settings = get_settings()
    access_payload = jwt.decode(
        body["access_token"],
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    refresh_payload = jwt.decode(
        body["refresh_token"],
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    assert access_payload["typ"] == "access"
    assert refresh_payload["typ"] == "refresh"
    assert refresh_payload["exp"] > access_payload["exp"]


def test_register_sends_verification_email_and_verify_endpoint_confirms_email(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    sent_urls: list[str] = []

    async def capture_verification_email(**kwargs):
        sent_urls.append(kwargs["verification_url"])

    monkeypatch.setattr(
        auth_service, "send_verification_email", capture_verification_email
    )

    register_response = client.post(
        "/auth/register",
        json={
            "username": "verifyme",
            "email": "verifyme@example.com",
            "password": VALID_PASSWORD,
        },
    )
    register_body = register_response.json()

    assert register_response.status_code == 201, register_response.text
    assert register_body["user"]["is_email_verified"] is False
    assert len(sent_urls) == 1
    assert "/verify-email?token=" in sent_urls[0]

    verify_response = client.post(
        "/auth/verify-email",
        json={"token": verification_token_from_url(sent_urls[0])},
    )
    profile_response = client.get(
        "/users/me", headers=bearer_headers(register_body["access_token"])
    )

    assert verify_response.status_code == 200, verify_response.text
    assert verify_response.json()["verified"] is True
    assert profile_response.status_code == 200
    assert profile_response.json()["is_email_verified"] is True


def test_register_sends_registration_email(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    sent_registration: list[dict] = []

    async def capture_registration_email(**kwargs):
        sent_registration.append(kwargs)

    monkeypatch.setattr(
        auth_service, "send_registration_email", capture_registration_email
    )

    response = client.post(
        "/auth/register",
        json={
            "username": "welcometest",
            "email": "welcometest@example.com",
            "password": VALID_PASSWORD,
        },
    )

    assert response.status_code == 201, response.text
    assert sent_registration == [
        {"to_address": "welcometest@example.com", "username": "welcometest"}
    ]


def test_verify_email_rejects_reused_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    sent_urls: list[str] = []

    async def capture_verification_email(**kwargs):
        sent_urls.append(kwargs["verification_url"])

    monkeypatch.setattr(
        auth_service, "send_verification_email", capture_verification_email
    )
    client.post(
        "/auth/register",
        json={
            "username": "verifyonce",
            "email": "verifyonce@example.com",
            "password": VALID_PASSWORD,
        },
    )
    token = verification_token_from_url(sent_urls[0])

    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200
    reused_response = client.post("/auth/verify-email", json={"token": token})

    assert reused_response.status_code == 400
    assert reused_response.json()["detail"] == "Invalid or expired verification token"


def test_resend_verification_is_throttled_after_registration(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    sent_urls: list[str] = []

    async def capture_verification_email(**kwargs):
        sent_urls.append(kwargs["verification_url"])

    monkeypatch.setattr(
        auth_service, "send_verification_email", capture_verification_email
    )
    register_response = client.post(
        "/auth/register",
        json={
            "username": "resendwait",
            "email": "resendwait@example.com",
            "password": VALID_PASSWORD,
        },
    )

    response = client.post(
        "/auth/resend-verification",
        headers=bearer_headers(register_response.json()["access_token"]),
    )

    assert response.status_code == 429
    assert response.json()["detail"] == (
        "Please wait before requesting another verification email"
    )
    assert len(sent_urls) == 1


def test_resend_verification_returns_already_verified(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    sent_urls: list[str] = []

    async def capture_verification_email(**kwargs):
        sent_urls.append(kwargs["verification_url"])

    monkeypatch.setattr(
        auth_service, "send_verification_email", capture_verification_email
    )
    register_response = client.post(
        "/auth/register",
        json={
            "username": "alreadyverified",
            "email": "alreadyverified@example.com",
            "password": VALID_PASSWORD,
        },
    )
    client.post(
        "/auth/verify-email",
        json={"token": verification_token_from_url(sent_urls[0])},
    )

    response = client.post(
        "/auth/resend-verification",
        headers=bearer_headers(register_response.json()["access_token"]),
    )

    assert response.status_code == 200
    assert response.json()["sent"] is False
    assert response.json()["message"] == "Email address is already verified"


def test_password_reset_request_sends_reset_email_and_confirm_sends_security_email(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    reset_urls: list[str] = []
    security_events: list[dict] = []

    async def capture_password_reset_email(**kwargs):
        reset_urls.append(kwargs["reset_url"])

    async def capture_security_email(**kwargs):
        security_events.append(kwargs)

    monkeypatch.setattr(
        auth_service, "send_password_reset_email", capture_password_reset_email
    )
    monkeypatch.setattr(auth_service, "send_security_email", capture_security_email)
    client.post(
        "/auth/register",
        json={
            "username": "resetuser",
            "email": "resetuser@example.com",
            "password": VALID_PASSWORD,
        },
    )

    request_response = client.post(
        "/auth/password-reset/request", json={"email": "resetuser@example.com"}
    )
    reset_token = reset_token_from_url(reset_urls[0])
    confirm_response = client.post(
        "/auth/password-reset/confirm",
        json={"token": reset_token, "password": "N3w!StrongPass"},
    )
    old_login = client.post(
        "/auth/login",
        json={"username_or_email": "resetuser", "password": VALID_PASSWORD},
    )
    new_login = client.post(
        "/auth/login",
        json={"username_or_email": "resetuser", "password": "N3w!StrongPass"},
    )

    assert request_response.status_code == 200, request_response.text
    assert "/reset-password?token=" in reset_urls[0]
    assert confirm_response.status_code == 200, confirm_response.text
    assert confirm_response.json()["message"] == "Password reset successfully"
    assert old_login.status_code == 401
    assert new_login.status_code == 200
    assert security_events == [
        {
            "to_address": "resetuser@example.com",
            "username": "resetuser",
            "event_label": "Your password was reset",
        }
    ]


def test_password_reset_request_is_throttled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    reset_urls: list[str] = []

    async def capture_password_reset_email(**kwargs):
        reset_urls.append(kwargs["reset_url"])

    monkeypatch.setattr(
        auth_service, "send_password_reset_email", capture_password_reset_email
    )
    client.post(
        "/auth/register",
        json={
            "username": "resetwait",
            "email": "resetwait@example.com",
            "password": VALID_PASSWORD,
        },
    )

    first_response = client.post(
        "/auth/password-reset/request", json={"email": "resetwait@example.com"}
    )
    second_response = client.post(
        "/auth/password-reset/request", json={"email": "resetwait@example.com"}
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 429
    assert second_response.json()["detail"] == (
        "Please wait before requesting another password reset email"
    )
    assert len(reset_urls) == 1


def test_password_reset_confirm_rejects_reused_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    reset_urls: list[str] = []

    async def capture_password_reset_email(**kwargs):
        reset_urls.append(kwargs["reset_url"])

    async def capture_security_email(**kwargs):
        del kwargs

    monkeypatch.setattr(
        auth_service, "send_password_reset_email", capture_password_reset_email
    )
    monkeypatch.setattr(auth_service, "send_security_email", capture_security_email)
    client.post(
        "/auth/register",
        json={
            "username": "resetonce",
            "email": "resetonce@example.com",
            "password": VALID_PASSWORD,
        },
    )
    client.post("/auth/password-reset/request", json={"email": "resetonce@example.com"})
    token = reset_token_from_url(reset_urls[0])

    assert (
        client.post(
            "/auth/password-reset/confirm",
            json={"token": token, "password": "N3w!StrongPass"},
        ).status_code
        == 200
    )
    reused_response = client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "password": "N3w!StrongPass2"},
    )

    assert reused_response.status_code == 400
    assert reused_response.json()["detail"] == "Invalid or expired reset token"


def test_password_reset_request_for_unknown_email_is_generic(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    reset_urls: list[str] = []

    async def capture_password_reset_email(**kwargs):
        reset_urls.append(kwargs["reset_url"])

    monkeypatch.setattr(
        auth_service, "send_password_reset_email", capture_password_reset_email
    )

    response = client.post(
        "/auth/password-reset/request", json={"email": "missing@example.com"}
    )

    assert response.status_code == 200
    assert response.json()["message"] == (
        "If an account exists for that email, a reset link has been sent"
    )
    assert reset_urls == []


def test_user_model_extends_base():
    assert issubclass(User, Base)
    assert User.metadata is Base.metadata


def test_register_normalizes_email_and_rejects_formatted_duplicate(
    client: TestClient,
):
    response = client.post(
        "/auth/register",
        json={
            "username": "emailcase",
            "email": "EmailCase@Example.COM",
            "password": VALID_PASSWORD,
        },
    )

    assert response.status_code == 201
    assert response.json()["user"]["email"] == "emailcase@example.com"

    duplicate_response = client.post(
        "/auth/register",
        json={
            "username": "emailcase2",
            "email": " emailcase@example.com ",
            "password": VALID_PASSWORD,
        },
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "User already exists"


def test_register_rejects_unsupported_email_domain(client: TestClient):
    response = client.post(
        "/auth/register",
        json={
            "username": "bademaildomain",
            "email": "bademaildomain@example.net",
            "password": VALID_PASSWORD,
        },
    )

    assert response.status_code == 422


def test_duplicate_register_fails(client: TestClient):
    payload = {
        "username": "duplicate",
        "email": "duplicate@example.com",
        "password": VALID_PASSWORD,
    }
    assert client.post("/auth/register", json=payload).status_code == 201
    response = client.post("/auth/register", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "User already exists"


def test_duplicate_username_returns_409(client: TestClient):
    assert (
        client.post(
            "/auth/register",
            json={
                "username": "sameuser",
                "email": "sameuser@example.com",
                "password": VALID_PASSWORD,
            },
        ).status_code
        == 201
    )
    response = client.post(
        "/auth/register",
        json={
            "username": "sameuser",
            "email": "different-email@example.com",
            "password": VALID_PASSWORD,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "User already exists"


def test_duplicate_email_returns_409(client: TestClient):
    assert (
        client.post(
            "/auth/register",
            json={
                "username": "emailowner",
                "email": "shared-email@example.com",
                "password": VALID_PASSWORD,
            },
        ).status_code
        == 201
    )
    response = client.post(
        "/auth/register",
        json={
            "username": "differentuser",
            "email": "shared-email@example.com",
            "password": VALID_PASSWORD,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "User already exists"


def test_register_rejects_short_password(client: TestClient):
    response = client.post(
        "/auth/register",
        json={
            "username": "shortpass",
            "email": "shortpass@example.com",
            "password": "short",
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "password",
    [
        "NoNumber!",
        "NoSpecial1",
        "A1!23456",
    ],
)
def test_register_rejects_weak_password(client: TestClient, password: str):
    response = client.post(
        "/auth/register",
        json={
            "username": f"weakpass{uuid4().hex[:8]}",
            "email": f"weakpass{uuid4().hex[:8]}@example.com",
            "password": password,
        },
    )

    assert response.status_code == 422


def test_register_rejects_invalid_username_and_email(client: TestClient):
    username_response = client.post(
        "/auth/register",
        json={
            "username": "bad username!",
            "email": "valid@example.com",
            "password": VALID_PASSWORD,
        },
    )
    email_response = client.post(
        "/auth/register",
        json={
            "username": "valid-user",
            "email": "not-an-email",
            "password": VALID_PASSWORD,
        },
    )

    assert username_response.status_code == 422
    assert email_response.status_code == 422


def test_login_success(client: TestClient):
    client.post(
        "/auth/register",
        json={
            "username": "loginuser",
            "email": "loginuser@example.com",
            "password": VALID_PASSWORD,
        },
    )
    response = client.post(
        "/auth/login",
        json={
            "username_or_email": "loginuser",
            "password": VALID_PASSWORD,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert "hashed_password" not in body
    assert "hashed_password" not in body["user"]


def test_login_bad_password_fails(client: TestClient):
    client.post(
        "/auth/register",
        json={
            "username": "badlogin",
            "email": "badlogin@example.com",
            "password": VALID_PASSWORD,
        },
    )
    response = client.post(
        "/auth/login",
        json={"username_or_email": "badlogin", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_logout_requires_current_access_token(client: TestClient):
    response = client.post("/auth/logout", json={})

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_logout_current_session_with_access_token_only(client: TestClient):
    register_response = client.post(
        "/auth/register",
        json={
            "username": "accesslogout",
            "email": "accesslogout@example.com",
            "password": VALID_PASSWORD,
        },
    )
    body = register_response.json()

    logout_response = client.post(
        "/auth/logout",
        headers=bearer_headers(body["access_token"]),
        json={},
    )
    profile_response = client.get(
        "/users/me", headers=bearer_headers(body["access_token"])
    )

    assert logout_response.status_code == 204
    assert profile_response.status_code == 200
    assert profile_response.json()["username"] == "accesslogout"


def test_refresh_token_rotation_blacklists_old_refresh_token(client: TestClient):
    register_response = client.post(
        "/auth/register",
        json={
            "username": "refreshuser",
            "email": "refreshuser@example.com",
            "password": VALID_PASSWORD,
        },
    )
    body = register_response.json()
    original_refresh_token = body["refresh_token"]

    refresh_response = client.post(
        "/auth/refresh", json={"refresh_token": original_refresh_token}
    )

    assert refresh_response.status_code == 200
    rotated_body = refresh_response.json()
    assert rotated_body["access_token"]
    assert rotated_body["refresh_token"] != original_refresh_token

    reuse_response = client.post(
        "/auth/refresh", json={"refresh_token": original_refresh_token}
    )
    profile_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {rotated_body['access_token']}"},
    )

    assert reuse_response.status_code == 401
    assert reuse_response.json()["detail"] == "Invalid refresh token"
    assert profile_response.status_code == 200
    assert profile_response.json()["username"] == "refreshuser"


def test_logout_blacklists_refresh_token(client: TestClient):
    register_response = client.post(
        "/auth/register",
        json={
            "username": "logoutuser",
            "email": "logoutuser@example.com",
            "password": VALID_PASSWORD,
        },
    )
    body = register_response.json()
    refresh_token = body["refresh_token"]

    logout_response = client.post(
        "/auth/logout",
        headers=bearer_headers(body["access_token"]),
        json={"refresh_token": refresh_token},
    )
    refresh_response = client.post(
        "/auth/refresh", json={"refresh_token": refresh_token}
    )

    assert logout_response.status_code == 204
    assert refresh_response.status_code == 401
    assert refresh_response.json()["detail"] == "Invalid refresh token"


def test_logout_rejects_refresh_token_for_another_user(client: TestClient):
    first_response = client.post(
        "/auth/register",
        json={
            "username": "logoutowner",
            "email": "logoutowner@example.com",
            "password": VALID_PASSWORD,
        },
    )
    second_response = client.post(
        "/auth/register",
        json={
            "username": "logoutother",
            "email": "logoutother@example.com",
            "password": VALID_PASSWORD,
        },
    )

    response = client.post(
        "/auth/logout",
        headers=bearer_headers(first_response.json()["access_token"]),
        json={"refresh_token": second_response.json()["refresh_token"]},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"


def test_list_active_sessions_includes_current_refresh_session(client: TestClient):
    register_response = client.post(
        "/auth/register",
        json={
            "username": "sessionlist",
            "email": "sessionlist@example.com",
            "password": VALID_PASSWORD,
        },
    )
    body = register_response.json()

    response = client.get(
        "/users/me/sessions", headers=bearer_headers(body["access_token"])
    )

    assert response.status_code == 200, response.text
    sessions = response.json()
    assert len(sessions) == 1
    assert sessions[0]["id"]
    assert sessions[0]["created_at"]
    assert sessions[0]["last_seen_at"]
    assert sessions[0]["expires_at"]


def test_revoke_individual_session_blocks_refresh_token(client: TestClient):
    register_response = client.post(
        "/auth/register",
        json={
            "username": "sessionrevoke",
            "email": "sessionrevoke@example.com",
            "password": VALID_PASSWORD,
        },
    )
    body = register_response.json()
    sessions = client.get(
        "/users/me/sessions", headers=bearer_headers(body["access_token"])
    ).json()

    revoke_response = client.delete(
        f"/users/me/sessions/{sessions[0]['id']}",
        headers=bearer_headers(body["access_token"]),
    )
    refresh_response = client.post(
        "/auth/refresh", json={"refresh_token": body["refresh_token"]}
    )
    list_response = client.get(
        "/users/me/sessions", headers=bearer_headers(body["access_token"])
    )

    assert revoke_response.status_code == 200, revoke_response.text
    assert revoke_response.json()["message"] == "Session revoked"
    assert refresh_response.status_code == 401
    assert refresh_response.json()["detail"] == "Invalid refresh token"
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_revoke_all_sessions_blocks_every_refresh_token(client: TestClient):
    register_response = client.post(
        "/auth/register",
        json={
            "username": "sessionendall",
            "email": "sessionendall@example.com",
            "password": VALID_PASSWORD,
        },
    )
    first_body = register_response.json()
    second_login = client.post(
        "/auth/login",
        json={"username_or_email": "sessionendall", "password": VALID_PASSWORD},
    )
    second_body = second_login.json()
    list_before = client.get(
        "/users/me/sessions", headers=bearer_headers(first_body["access_token"])
    )

    revoke_response = client.delete(
        "/users/me/sessions", headers=bearer_headers(first_body["access_token"])
    )
    first_refresh = client.post(
        "/auth/refresh", json={"refresh_token": first_body["refresh_token"]}
    )
    second_refresh = client.post(
        "/auth/refresh", json={"refresh_token": second_body["refresh_token"]}
    )
    list_after = client.get(
        "/users/me/sessions", headers=bearer_headers(first_body["access_token"])
    )

    assert list_before.status_code == 200
    assert len(list_before.json()) == 2
    assert revoke_response.status_code == 200, revoke_response.text
    assert revoke_response.json()["message"] == "All sessions revoked"
    assert first_refresh.status_code == 401
    assert second_refresh.status_code == 401
    assert list_after.status_code == 200
    assert list_after.json() == []


def test_refresh_token_cannot_be_used_as_access_token(client: TestClient):
    register_response = client.post(
        "/auth/register",
        json={
            "username": "refreshnotaccess",
            "email": "refreshnotaccess@example.com",
            "password": VALID_PASSWORD,
        },
    )
    refresh_token = register_response.json()["refresh_token"]

    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {refresh_token}"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_password_hashing_uses_argon2():
    from flipradar.api.dependencies.auth import hash_password, verify_password

    hashed_password = hash_password(VALID_PASSWORD)

    assert hashed_password.startswith("$argon2")
    assert verify_password(VALID_PASSWORD, hashed_password)
    assert not verify_password(VALID_PASSWORD.lower(), hashed_password)


def test_bad_token_returns_401(client: TestClient):
    response = client.get(
        "/auth/me", headers={"Authorization": "Bearer not-a-valid-token"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_expired_token_returns_401(client: TestClient):
    settings = get_settings()
    expired_token = jwt.encode(
        {
            "sub": str(uuid4()),
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_auth_me_works_with_token(client: TestClient):
    headers = auth_headers(client, "profileuser")
    response = client.get("/auth/me", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "profileuser"
    assert "hashed_password" not in body


def test_users_me_works_with_token(client: TestClient):
    headers = auth_headers(client, "usersprofile")
    response = client.get("/users/me", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "usersprofile"
    assert body["display_name"] == "usersprofile"
    assert body["is_email_verified"] is False
    assert "hashed_password" not in body


def test_update_users_me_display_name(client: TestClient):
    headers = auth_headers(client, "settingsprofile")

    response = client.patch(
        "/users/me",
        headers=headers,
        json={"display_name": "  Settings Collector  "},
    )

    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == "Settings Collector"


def test_change_password_requires_current_password(client: TestClient):
    headers = auth_headers(client, "passwordsettings")

    response = client.post(
        "/users/me/password",
        headers=headers,
        json={
            "current_password": "wrong-password",
            "new_password": "N3w!StrongPass",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect"


def test_change_password_updates_login_and_sends_security_email(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    security_events: list[dict] = []

    async def capture_security_email(**kwargs):
        security_events.append(kwargs)

    monkeypatch.setattr(auth_service, "send_security_email", capture_security_email)
    headers = auth_headers(client, "passwordchanged")

    response = client.post(
        "/users/me/password",
        headers=headers,
        json={
            "current_password": VALID_PASSWORD,
            "new_password": "N3w!StrongPass",
        },
    )
    old_login = client.post(
        "/auth/login",
        json={"username_or_email": "passwordchanged", "password": VALID_PASSWORD},
    )
    new_login = client.post(
        "/auth/login",
        json={"username_or_email": "passwordchanged", "password": "N3w!StrongPass"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Password changed successfully"
    assert old_login.status_code == 401
    assert new_login.status_code == 200
    assert security_events == [
        {
            "to_address": "passwordchanged@example.com",
            "username": "passwordchanged",
            "event_label": "Your password was changed",
        }
    ]


def test_account_deletion_requires_current_password(client: TestClient):
    headers = auth_headers(client, "deletionwrongpass")

    response = client.post(
        "/users/me/deletion-request",
        headers=headers,
        json={"current_password": "wrong-password"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect"


def test_account_deletion_schedules_removal_and_sends_confirmation_email(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    deletion_emails: list[dict] = []

    async def capture_deletion_email(**kwargs):
        deletion_emails.append(kwargs)

    monkeypatch.setattr(
        auth_service,
        "send_account_deletion_confirmation_email",
        capture_deletion_email,
    )
    headers = auth_headers(client, "deletionuser")

    response = client.post(
        "/users/me/deletion-request",
        headers=headers,
        json={"current_password": VALID_PASSWORD},
    )
    profile_response = client.get("/users/me", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    scheduled_at = datetime.fromisoformat(body["deletion_scheduled_at"])
    requested_at = datetime.fromisoformat(
        profile_response.json()["deletion_requested_at"]
    )
    assert body["message"] == (
        "Account deletion confirmed. Your user data is scheduled for removal in 24 hours."
    )
    assert scheduled_at.replace(tzinfo=None) - requested_at.replace(
        tzinfo=None
    ) == timedelta(hours=24)
    profile_scheduled_at = datetime.fromisoformat(
        profile_response.json()["deletion_scheduled_at"]
    )
    assert profile_scheduled_at.replace(tzinfo=None) == scheduled_at.replace(
        tzinfo=None
    )
    assert deletion_emails[0]["to_address"] == "deletionuser@example.com"
    assert deletion_emails[0]["username"] == "deletionuser"
    emailed_scheduled_at = datetime.fromisoformat(
        deletion_emails[0]["deletion_scheduled_at"]
    )
    assert emailed_scheduled_at.replace(tzinfo=None) == scheduled_at.replace(
        tzinfo=None
    )


def test_email_change_request_sends_new_confirmation_and_old_security_notice(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    confirmation_urls: list[str] = []
    security_events: list[dict] = []

    async def capture_email_change_confirmation(**kwargs):
        confirmation_urls.append(kwargs["confirmation_url"])
        assert kwargs["to_address"] == "next-email@example.com"
        assert kwargs["new_email"] == "next-email@example.com"

    async def capture_security_email(**kwargs):
        security_events.append(kwargs)

    monkeypatch.setattr(
        auth_service,
        "send_email_change_confirmation_email",
        capture_email_change_confirmation,
    )
    monkeypatch.setattr(auth_service, "send_security_email", capture_security_email)
    headers = auth_headers(client, "emailsettings")

    response = client.post(
        "/users/me/email-change/request",
        headers=headers,
        json={
            "new_email": " Next-Email@Example.COM ",
            "current_password": VALID_PASSWORD,
        },
    )
    profile_response = client.get("/users/me", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Confirmation email sent to the new address"
    assert len(confirmation_urls) == 1
    assert "/verify-email?token=" in confirmation_urls[0]
    assert "flow=email-change" in confirmation_urls[0]
    assert profile_response.json()["email"] == "emailsettings@example.com"
    assert profile_response.json()["pending_email"] == "next-email@example.com"
    assert security_events == [
        {
            "to_address": "emailsettings@example.com",
            "username": "emailsettings",
            "event_label": "Email change requested for next-email@example.com",
        }
    ]


def test_email_change_confirmation_applies_new_email_after_verification(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    confirmation_urls: list[str] = []

    async def capture_email_change_confirmation(**kwargs):
        confirmation_urls.append(kwargs["confirmation_url"])

    async def capture_security_email(**kwargs):
        del kwargs

    monkeypatch.setattr(
        auth_service,
        "send_email_change_confirmation_email",
        capture_email_change_confirmation,
    )
    monkeypatch.setattr(auth_service, "send_security_email", capture_security_email)
    headers = auth_headers(client, "emailconfirm")
    client.post(
        "/users/me/email-change/request",
        headers=headers,
        json={
            "new_email": "emailconfirm-next@example.com",
            "current_password": VALID_PASSWORD,
        },
    )
    token = email_change_token_from_url(confirmation_urls[0])

    confirm_response = client.post("/auth/email-change/confirm", json={"token": token})
    profile_response = client.get("/users/me", headers=headers)
    old_email_login = client.post(
        "/auth/login",
        json={
            "username_or_email": "emailconfirm@example.com",
            "password": VALID_PASSWORD,
        },
    )
    new_email_login = client.post(
        "/auth/login",
        json={
            "username_or_email": "emailconfirm-next@example.com",
            "password": VALID_PASSWORD,
        },
    )

    assert confirm_response.status_code == 200, confirm_response.text
    assert confirm_response.json()["message"] == "Email address changed successfully"
    assert profile_response.json()["email"] == "emailconfirm-next@example.com"
    assert profile_response.json()["pending_email"] is None
    assert profile_response.json()["is_email_verified"] is True
    assert old_email_login.status_code == 401
    assert new_email_login.status_code == 200


def test_email_change_request_is_throttled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    confirmation_urls: list[str] = []

    async def capture_email_change_confirmation(**kwargs):
        confirmation_urls.append(kwargs["confirmation_url"])

    async def capture_security_email(**kwargs):
        del kwargs

    monkeypatch.setattr(
        auth_service,
        "send_email_change_confirmation_email",
        capture_email_change_confirmation,
    )
    monkeypatch.setattr(auth_service, "send_security_email", capture_security_email)
    headers = auth_headers(client, "emailwait")

    first_response = client.post(
        "/users/me/email-change/request",
        headers=headers,
        json={
            "new_email": "emailwait-next@example.com",
            "current_password": VALID_PASSWORD,
        },
    )
    second_response = client.post(
        "/users/me/email-change/request",
        headers=headers,
        json={
            "new_email": "emailwait-other@example.com",
            "current_password": VALID_PASSWORD,
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 429
    assert second_response.json()["detail"] == (
        "Please wait before requesting another email change"
    )
    assert len(confirmation_urls) == 1


def test_email_change_rejects_existing_email(client: TestClient):
    headers = auth_headers(client, "emailduplicate")
    auth_headers(client, "emailtaken")

    response = client.post(
        "/users/me/email-change/request",
        headers=headers,
        json={
            "new_email": "emailtaken@example.com",
            "current_password": VALID_PASSWORD,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already exists"


def test_users_me_requires_token(client: TestClient):
    response = client.get("/users/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_portfolio_requires_token(client: TestClient):
    response = client.get("/portfolio")

    assert response.status_code == 401


def test_portfolio_add_list_summary_delete(client: TestClient):
    lego_set = create_lego_set(client, "75192")
    snapshot_payload = create_snapshot_payload("75192", fair_value="625.00")
    snapshot_payload.update({"median_price": "625.00", "listing_count": 22})
    client.post("/snapshots", json=snapshot_payload)
    headers = auth_headers(client, "portfolio-user")

    add_response = client.post(
        "/portfolio/items",
        headers=headers,
        json={
            "set_number": lego_set["set_number"],
            "quantity": 2,
            "purchase_price": "500.00",
            "condition": "sealed",
            "notes": "Demo holding",
        },
    )

    assert add_response.status_code == 201, add_response.text
    item = add_response.json()
    assert item["set_number"] == "75192"
    assert item["valuation_status"] == "valued"
    assert item["current_total_value"] == "1250.00"

    list_response = client.get("/portfolio", headers=headers)
    assert list_response.status_code == 200
    assert len(collection_data(list_response)) == 1

    summary_response = client.get("/portfolio/summary", headers=headers)
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["total_items"] == 1
    assert summary["total_sets"] == 1
    assert summary["total_quantity"] == 2
    assert summary["total_cost_basis"] == "1000.00"
    assert summary["estimated_current_value"] == "1250.00"

    delete_response = client.delete(f"/portfolio/items/{item['id']}", headers=headers)
    assert delete_response.status_code == 204
    assert client.get("/portfolio", headers=headers).json()["data"] == []


def test_portfolio_holding_detail_returns_analytics_and_is_user_scoped(
    client: TestClient,
):
    def metric_snapshot(set_number: str, value: str, condition: str = "new") -> dict:
        return {
            "set_number": set_number,
            "marketplace_name": "ebay",
            "condition": condition,
            "currency": "USD",
            "metric_type": "fair_market_value",
            "value": value,
            "sample_size": 12,
        }

    create_lego_set(client, "10300")
    create_lego_set(client, "10301")
    assert (
        client.post("/snapshots", json=metric_snapshot("10300", "200.00")).status_code
        == 201
    )
    client.post(
        "/snapshots",
        json=metric_snapshot("10300", "125.00", "used_complete"),
    )
    assert (
        client.post("/snapshots", json=metric_snapshot("10301", "100.00")).status_code
        == 201
    )
    headers = auth_headers(client, "holding-detail-user")
    item = client.post(
        "/portfolio/items",
        headers=headers,
        json={
            "set_number": "10300",
            "quantity": 1,
            "purchase_price": "150.00",
            "condition": "new",
            "purchase_date": "2025-01-15T00:00:00Z",
            "notes": "Bought during a sale",
        },
    ).json()
    client.post(
        "/portfolio/items",
        headers=headers,
        json={
            "set_number": "10301",
            "quantity": 1,
            "purchase_price": "80.00",
            "condition": "new",
        },
    )

    response = client.get(f"/portfolio/items/{item['id']}/detail", headers=headers)

    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["holding"]["notes"] == "Bought during a sale"
    assert detail["holding"]["current_total_value"] == "200.00"
    assert detail["holding"]["unrealized_gain_loss_percent"] == "33.33"
    assert detail["portfolio_total_value"] == "300.00"
    assert detail["portfolio_share_percent"] == "66.67"
    assert detail["concentration_risk"]["level"] == "high"
    assert detail["market_freshness_at"] is not None
    assert len(detail["market_snapshots"]) == 2
    assert {row["condition"] for row in detail["condition_pricing"]} == {
        "new",
        "used",
        "incomplete",
    }
    assert (
        next(row for row in detail["condition_pricing"] if row["condition"] == "used")[
            "estimated_unit_value"
        ]
        == "125.00"
    )

    other_headers = auth_headers(client, "holding-detail-other-user")
    assert (
        client.get(
            f"/portfolio/items/{item['id']}/detail", headers=other_headers
        ).status_code
        == 404
    )


def test_portfolio_update_item_with_patch_and_put(client: TestClient):
    create_lego_set(client, "10305")
    create_lego_set(client, "21325")
    client.post(
        "/snapshots",
        json={
            **create_snapshot_payload("21325", fair_value="240.00"),
            "median_price": "240.00",
            "listing_count": 10,
        },
    )
    headers = auth_headers(client, "portfolio-update-user")
    item = client.post(
        "/portfolio/items",
        headers=headers,
        json={
            "set_number": "10305",
            "quantity": 1,
            "purchase_price": "150.00",
            "condition": "used",
            "notes": "Original",
        },
    ).json()

    patch_response = client.patch(
        f"/portfolio/items/{item['id']}",
        headers=headers,
        json={"quantity": 2, "purchase_price": "175.00", "notes": "Patched"},
    )
    assert patch_response.status_code == 200, patch_response.text
    patched = patch_response.json()
    assert patched["quantity"] == 2
    assert patched["purchase_price"] == "175.00"
    assert patched["notes"] == "Patched"
    assert patched["cost_basis"] == "350.00"

    put_response = client.put(
        f"/portfolio/items/{item['id']}",
        headers=headers,
        json={
            "set_number": "21325",
            "quantity": 3,
            "purchase_price": "200.00",
            "condition": "new",
            "notes": "Moved to another set",
        },
    )
    assert put_response.status_code == 200, put_response.text
    updated = put_response.json()
    assert updated["set_number"] == "21325"
    assert updated["quantity"] == 3
    assert updated["condition"] == "new"
    assert updated["current_total_value"] == "720.00"
    assert updated["unrealized_gain_loss"] == "120.00"


def test_portfolio_item_access_is_user_scoped(client: TestClient):
    create_lego_set(client, "10497")
    owner_headers = auth_headers(client, "portfolio-owner")
    other_headers = auth_headers(client, "portfolio-other")
    item = client.post(
        "/portfolio/items",
        headers=owner_headers,
        json={
            "set_number": "10497",
            "quantity": 1,
            "purchase_price": "90.00",
            "condition": "used",
        },
    ).json()

    other_list = client.get("/portfolio", headers=other_headers)
    assert other_list.status_code == 200
    assert other_list.json()["data"] == []

    other_patch = client.patch(
        f"/portfolio/items/{item['id']}",
        headers=other_headers,
        json={"quantity": 5},
    )
    assert other_patch.status_code == 404
    assert other_patch.json()["detail"] == "Portfolio item not found"

    owner_list = client.get("/portfolio", headers=owner_headers).json()["data"]
    assert len(owner_list) == 1
    assert owner_list[0]["id"] == item["id"]
    assert owner_list[0]["quantity"] == 1


def test_portfolio_list_supports_pagination_and_condition_filter(
    client: TestClient,
):
    create_lego_set(client, "110001")
    create_lego_set(client, "110002")
    headers = auth_headers(client, "portfolio-pagination")
    assert (
        client.post(
            "/portfolio/items",
            headers=headers,
            json={
                "set_number": "110001",
                "quantity": 1,
                "purchase_price": "100.00",
                "condition": "new",
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/portfolio/items",
            headers=headers,
            json={
                "set_number": "110002",
                "quantity": 1,
                "purchase_price": "90.00",
                "condition": "used",
            },
        ).status_code
        == 201
    )

    response = client.get(
        "/portfolio", headers=headers, params={"condition": "used", "limit": 1}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["count"] == 1
    assert body["data"][0]["set_number"] == "110002"


def test_portfolio_delete_is_ownership_protected(client: TestClient):
    create_lego_set(client, "10295")
    owner_headers = auth_headers(client, "portfolio-delete-owner")
    other_headers = auth_headers(client, "portfolio-delete-other")
    item = client.post(
        "/portfolio/items",
        headers=owner_headers,
        json={
            "set_number": "10295",
            "quantity": 1,
            "purchase_price": "120.00",
            "condition": "sealed",
        },
    ).json()

    other_delete = client.delete(
        f"/portfolio/items/{item['id']}", headers=other_headers
    )
    assert other_delete.status_code == 404
    assert other_delete.json()["detail"] == "Portfolio item not found"

    owner_list = client.get("/portfolio", headers=owner_headers)
    assert owner_list.status_code == 200
    assert [owned_item["id"] for owned_item in owner_list.json()["data"]] == [
        item["id"]
    ]

    owner_delete = client.delete(
        f"/portfolio/items/{item['id']}", headers=owner_headers
    )
    assert owner_delete.status_code == 204


def test_portfolio_summary_empty_portfolio(client: TestClient):
    headers = auth_headers(client, "empty-portfolio-user")

    response = client.get("/portfolio/summary", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "total_items": 0,
        "total_sets": 0,
        "total_quantity": 0,
        "total_cost_basis": "0.00",
        "estimated_current_value": "0.00",
        "unrealized_gain_loss": "0.00",
        "unrealized_gain_loss_percent": None,
        "holdings": [],
    }


def test_portfolio_history_returns_a_user_interpretable_unavailable_message(
    client: TestClient,
):
    response = client.get(
        "/portfolio/history", headers=auth_headers(client, "history-empty-user")
    )
    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Portfolio history is unavailable until at least two valuation snapshots "
        "have been recorded."
    )


def test_portfolio_history_endpoint_returns_requested_range_and_points(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    async def fake_history(db, user_id, history_range):
        del db, user_id
        return {
            "range": history_range,
            "points": [
                {
                    "timestamp": "2026-07-28T12:00:00Z",
                    "cost_basis": "100.00",
                    "market_value": "120.00",
                    "gain_loss": "20.00",
                    "currency": "USD",
                },
                {
                    "timestamp": "2026-07-29T12:00:00Z",
                    "cost_basis": "100.00",
                    "market_value": "125.00",
                    "gain_loss": "25.00",
                    "currency": "USD",
                },
            ],
        }

    monkeypatch.setattr(
        portfolio_service, "get_portfolio_valuation_history", fake_history
    )
    response = client.get(
        "/portfolio/history",
        headers=auth_headers(client, "history-api-user"),
        params={"range": "1w"},
    )

    assert response.status_code == 200
    assert response.json()["range"] == "1w"
    assert response.json()["points"][-1]["market_value"] == "125.00"


def test_portfolio_dashboard_endpoint_returns_one_combined_payload(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    async def fake_dashboard(db, user_id, **kwargs):
        del db, user_id
        assert kwargs["history_range"] == "1w"
        return {
            "portfolio": {
                "data": [],
                "pagination": {"limit": 25, "offset": 0, "count": 0, "has_more": False},
            },
            "summary": {
                "total_items": 0,
                "total_sets": 0,
                "total_quantity": 0,
                "total_cost_basis": "0.00",
                "estimated_current_value": "0.00",
                "unrealized_gain_loss": "0.00",
                "unrealized_gain_loss_percent": None,
                "holdings": [],
            },
            "history": None,
            "history_unavailable": "Portfolio history is unavailable until at least two valuation snapshots have been recorded.",
        }

    monkeypatch.setattr(portfolio_service, "get_portfolio_dashboard", fake_dashboard)
    response = client.get(
        "/portfolio/dashboard",
        headers=auth_headers(client, "dashboard-api-user"),
        params={"range": "1w"},
    )

    assert response.status_code == 200
    assert response.json()["portfolio"]["pagination"]["count"] == 0
    assert response.json()["history"] is None


def test_portfolio_summary_missing_snapshot_does_not_crash(client: TestClient):
    lego_set = create_lego_set(client, "42071")
    headers = auth_headers(client, "missing-market-user")
    response = client.post(
        "/portfolio/items",
        headers=headers,
        json={
            "set_number": lego_set["set_number"],
            "quantity": 1,
            "purchase_price": "100.00",
            "condition": "used",
        },
    )
    assert response.status_code == 201

    summary_response = client.get("/portfolio/summary", headers=headers)
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["estimated_current_value"] == "0.00"
    assert summary["unrealized_gain_loss"] == "0.00"
    assert summary["unrealized_gain_loss_percent"] is None
    assert summary["holdings"][0]["valuation_status"] == "missing_market_data"


def test_portfolio_summary_handles_quantities_prices_and_conditions(
    client: TestClient,
):
    create_lego_set(client, "10316")
    new_snapshot = create_snapshot_payload("10316", fair_value="200.00")
    new_snapshot.update(
        {
            "marketplace_name": "ebay",
            "condition": "new",
            "median_price": "200.00",
            "average_price": "200.00",
            "listing_count": 12,
        }
    )
    used_snapshot = create_snapshot_payload("10316", fair_value="100.00")
    used_snapshot.update(
        {
            "marketplace_name": "bricklink",
            "condition": "used",
            "median_price": "100.00",
            "average_price": "100.00",
            "listing_count": 8,
        }
    )
    assert client.post("/snapshots", json=new_snapshot).status_code == 201
    assert client.post("/snapshots", json=used_snapshot).status_code == 201
    headers = auth_headers(client, "portfolio-summary-user")

    for payload in [
        {
            "set_number": "10316",
            "quantity": 2,
            "purchase_price": "150.00",
            "condition": "new",
        },
        {
            "set_number": "10316",
            "quantity": 1,
            "purchase_price": "160.00",
            "condition": "new",
        },
        {
            "set_number": "10316",
            "quantity": 3,
            "purchase_price": "80.00",
            "condition": "used",
        },
    ]:
        response = client.post("/portfolio/items", headers=headers, json=payload)
        assert response.status_code == 201, response.text

    response = client.get("/portfolio/summary", headers=headers)

    assert response.status_code == 200
    summary = response.json()
    assert summary["total_items"] == 3
    assert summary["total_sets"] == 1
    assert summary["total_quantity"] == 6
    assert summary["total_cost_basis"] == "700.00"
    assert summary["estimated_current_value"] == "900.00"
    assert summary["unrealized_gain_loss"] == "200.00"
    assert summary["unrealized_gain_loss_percent"] == "28.57"

    holdings_by_condition = {
        holding["condition"]: holding for holding in summary["holdings"]
    }
    assert holdings_by_condition["new"]["quantity"] == 3
    assert holdings_by_condition["new"]["cost_basis"] == "460.00"
    assert holdings_by_condition["new"]["estimated_current_value"] == "600.00"
    assert holdings_by_condition["new"]["unrealized_gain_loss"] == "140.00"
    assert holdings_by_condition["used"]["quantity"] == 3
    assert holdings_by_condition["used"]["cost_basis"] == "240.00"
    assert holdings_by_condition["used"]["estimated_current_value"] == "300.00"
    assert holdings_by_condition["used"]["unrealized_gain_loss"] == "60.00"


def test_portfolio_purchase_details_filters_and_valuation_sorts(client: TestClient):
    icons = create_set_payload("10300")
    technic = create_set_payload("42100")
    technic.update({"theme": "Technic", "release_year": 2020})
    assert client.post("/sets", json=icons).status_code == 201
    assert client.post("/sets", json=technic).status_code == 201
    for set_number, value in (("10300", "200.00"), ("42100", "50.00")):
        response = client.post(
            "/snapshots",
            json={
                "set_number": set_number,
                "marketplace_name": "ebay",
                "condition": "new",
                "currency": "USD",
                "metric_type": "fair_market_value",
                "value": value,
                "sample_size": 10,
            },
        )
        assert response.status_code == 201, response.text

    headers = auth_headers(client, "portfolio-filter-user")
    payloads = [
        {
            "set_number": "10300",
            "quantity": 1,
            "purchase_price": "100.00",
            "condition": "new",
            "purchase_date": "2024-01-10T00:00:00Z",
            "currency": "USD",
        },
        {
            "set_number": "10300",
            "quantity": 1,
            "purchase_price": "150.00",
            "condition": "new",
            "purchase_date": "2024-02-10T00:00:00Z",
            "currency": "USD",
        },
        {
            "set_number": "42100",
            "quantity": 1,
            "purchase_price": "100.00",
            "condition": "new",
            "purchase_date": "2020-03-10T00:00:00Z",
            "currency": "USD",
        },
    ]
    for payload in payloads:
        response = client.post("/portfolio/items", headers=headers, json=payload)
        assert response.status_code == 201, response.text

    filtered = client.get(
        "/portfolio",
        headers=headers,
        params={"theme": "Icons", "year": 2024, "condition": "new"},
    )
    assert filtered.status_code == 200
    assert len(collection_data(filtered)) == 2

    gains = client.get(
        "/portfolio",
        headers=headers,
        params={"performance": "gain", "order": "gain_desc"},
    )
    gain_items = collection_data(gains)
    assert [item["purchase_price"] for item in gain_items] == ["100.00", "150.00"]
    assert gain_items[0]["unrealized_gain_loss_percent"] == "100.00"

    losses = client.get("/portfolio", headers=headers, params={"performance": "loss"})
    assert [item["set_number"] for item in collection_data(losses)] == ["42100"]

    purchase_dates = client.get(
        "/portfolio", headers=headers, params={"order": "purchase_date_asc", "limit": 1}
    )
    first_item = collection_data(purchase_dates)[0]
    assert first_item["set_number"] == "42100"
    assert first_item["purchase_date"].startswith("2020-03-10")
    assert first_item["currency"] == "USD"

    summary = client.get("/portfolio/summary", headers=headers).json()
    assert summary["estimated_current_value"] == "450.00"
    assert summary["unrealized_gain_loss"] == "100.00"
    assert summary["unrealized_gain_loss_percent"] == "28.57"


def test_set_detail_returns_metadata_and_latest_snapshot(client: TestClient):
    lego_set = create_lego_set(client, "75313")
    snapshot = client.post(
        "/snapshots", json=create_snapshot_payload("75313", fair_value="700.00")
    ).json()

    response = client.get(f"/sets/{lego_set['set_number']}")

    assert response.status_code == 200
    body = response.json()
    assert body["set_number"] == "75313"
    assert body["latest_snapshot"]["id"] == snapshot["id"]
    assert body["fair_value"] == "150.00"
    assert body["market_low"] == "120.00"
    assert body["market_high"] == "1000.00"
    assert body["valuation_status"] == "valued"


def test_set_detail_missing_snapshot_returns_null_valuation(client: TestClient):
    create_lego_set(client, "42071")
    response = client.get("/sets/42071")

    assert response.status_code == 200
    body = response.json()
    assert body["latest_snapshot"] is None
    assert body["fair_value"] is None
    assert body["valuation_status"] == "missing_market_data"


def test_set_detail_missing_set_returns_404(client: TestClient):
    response = client.get("/sets/00000")

    assert response.status_code == 404
    assert response.json()["detail"] == "LEGO set not found"


def test_analyze_endpoint(client: TestClient):
    lego_set = create_lego_set(client)
    client.post("/snapshots", json=create_snapshot_payload(lego_set["set_number"]))
    response = client.post(
        "/analyze",
        json={
            "set_number": int(lego_set["set_number"]),
            "user_goal": "buy_vs_pass",
            "asking_price": "125.00",
        },
    )

    logger.info(f"API TEST: POST /analyze status={response.status_code}")
    assert response.status_code == 201
    body = response.json()
    assert body["set_number"] == lego_set["set_number"]
    assert body["user_goal"] == "buy_vs_pass"
    assert body["asking_price"] == 125.0
    assert body["recommendation"] == "BUY"
    assert body["fair_value"] == 150.0
    assert body["score"] == 78
    assert body["confidence"] == "medium"
    assert (
        body["reasoning"]
        == "The all-in price is $125.00, compared with an estimated fair value of "
        "$150.00. This is a 16.7% discount to fair value, with an estimated ROI "
        "of 4.4%."
    )
    assert body["reason_codes"] == ["strong_discount", "medium_confidence_data"]
    assert body["all_in_price"] == 125.0
    assert body["discount_pct"] == 16.67
    assert body["estimated_profit"] == 5.5
    assert body["estimated_roi_pct"] == 4.4
    assert body["target_buy_price"] == 127.5


def test_post_analyze_returns_buy_when_asking_price_is_below_fair_value(
    client: TestClient,
):
    lego_set = create_lego_set(client)
    snapshot_payload = create_snapshot_payload(lego_set["set_number"])
    snapshot_payload.update(
        {
            "median_price": "200.00",
            "average_price": "210.00",
            "listing_count": 24,
        }
    )
    client.post("/snapshots", json=snapshot_payload)

    response = client.post(
        "/analyze",
        json={
            "set_number": lego_set["set_number"],
            "user_goal": "buy",
            "asking_price": "160.00",
        },
    )

    logger.info(
        f"API TEST: POST /analyze below fair value status={response.status_code}"
    )
    assert response.status_code == 201
    body = response.json()
    assert body["recommendation"] == "BUY"
    assert body["fair_value"] == 200.0
    assert body["score"] == 98
    assert body["confidence"] == "high"


def test_post_analyze_returns_pass_when_asking_price_is_above_fair_value(
    client: TestClient,
):
    lego_set = create_lego_set(client)
    snapshot_payload = create_snapshot_payload(lego_set["set_number"])
    snapshot_payload.update(
        {
            "median_price": "150.00",
            "average_price": "145.00",
            "listing_count": 24,
        }
    )
    client.post("/snapshots", json=snapshot_payload)

    response = client.post(
        "/analyze",
        json={
            "set_number": lego_set["set_number"],
            "user_goal": "buy",
            "asking_price": "180.00",
        },
    )

    logger.info(
        f"API TEST: POST /analyze above fair value status={response.status_code}"
    )
    assert response.status_code == 201
    body = response.json()
    assert body["recommendation"] == "PASS"
    assert body["fair_value"] == 150.0
    assert body["score"] == 18
    assert body["confidence"] == "high"
    assert (
        body["reasoning"]
        == "The all-in price is $180.00, compared with an estimated fair value of "
        "$150.00. This is a -20.0% discount to fair value, with an estimated ROI "
        "of -27.5%."
    )


def test_analyze_endpoint_accepts_buy_goal(client: TestClient):
    create_lego_set(client, "75192")
    snapshot_payload = create_snapshot_payload("75192", fair_value="625.00")
    snapshot_payload.update(
        {
            "low_price": "590.00",
            "median_price": "625.00",
            "average_price": "635.00",
            "high_price": "700.00",
            "listing_count": 22,
        }
    )
    client.post("/snapshots", json=snapshot_payload)
    response = client.post(
        "/analyze",
        json={
            "set_number": "75192",
            "user_goal": "buy",
            "asking_price": 550.00,
        },
    )

    logger.info(f"API TEST: POST /analyze buy goal status={response.status_code}")
    assert response.status_code == 201
    body = response.json()
    assert body["set_number"] == "75192"
    assert body["user_goal"] == "buy"
    assert body["asking_price"] == 550.0
    assert body["fair_value"] == 625.0
    assert body["score"] == 81
    assert body["recommendation"] == "BUY"
    assert body["confidence"] == "high"
    assert body["reasoning"] == (
        "The all-in price is $550.00, compared with an estimated fair value of "
        "$625.00. This is a 12.0% discount to fair value, with an estimated ROI "
        "of -1.1%."
    )
    assert body["market_low"] == 590.0
    assert body["market_high"] == 700.0
    assert body["listing_count"] == 22
    assert body["reason_codes"] == [
        "strong_discount",
        "negative_estimated_roi",
        "below_market_low",
        "high_confidence_data",
        "strong_market_depth",
    ]
    assert body["all_in_price"] == 550.0
    assert body["discount_pct"] == 12.0
    assert body["estimated_profit"] == -6.25
    assert body["estimated_roi_pct"] == -1.14
    assert body["target_buy_price"] == 531.25


def test_analyze_endpoint_returns_404_for_missing_set(
    client: TestClient, caplog: pytest.LogCaptureFixture
):
    caplog.set_level(logging.INFO)
    response = client.post(
        "/analyze",
        json={
            "set_number": "999999",
            "user_goal": "buy",
            "asking_price": 100.00,
        },
    )

    logger.info(f"API TEST: POST /analyze missing set status={response.status_code}")
    assert response.status_code == 404
    assert response.json()["detail"] == "LEGO set not found."
    assert "missing set set_number=999999" in caplog.text
    assert "error_type=RecommendationNotFoundError" in caplog.text


def test_post_analyze_returns_404_when_lego_set_does_not_exist(client: TestClient):
    response = client.post(
        "/analyze",
        json={
            "set_number": "404404",
            "user_goal": "buy",
            "asking_price": "100.00",
        },
    )

    logger.info(
        f"API TEST: POST /analyze nonexistent set status={response.status_code}"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "LEGO set not found."


def test_analyze_endpoint_without_snapshots_returns_low_confidence(
    client: TestClient, caplog: pytest.LogCaptureFixture
):
    caplog.set_level(logging.INFO)
    lego_set = create_lego_set(client)
    response = client.post(
        "/analyze",
        json={
            "set_number": lego_set["set_number"],
            "user_goal": "buy",
            "asking_price": 100.00,
        },
    )

    logger.info(f"API TEST: POST /analyze no snapshots status={response.status_code}")
    assert response.status_code == 201
    body = response.json()
    assert body["set_number"] == lego_set["set_number"]
    assert body["fair_value"] == 0.0
    assert body["score"] == 40
    assert body["recommendation"] == "WATCH"
    assert body["confidence"] == "low"
    assert body["reasoning"] == (
        "Not enough market data is available to estimate fair value."
    )
    assert f"missing snapshots set_number={lego_set['set_number']}" in caplog.text
    assert "snapshot_count=0" in caplog.text


def test_analyze_endpoint_requires_asking_price_for_buy_goal(
    client: TestClient, caplog: pytest.LogCaptureFixture
):
    caplog.set_level(logging.INFO)
    lego_set = create_lego_set(client)
    client.post("/snapshots", json=create_snapshot_payload(lego_set["set_number"]))

    response = client.post(
        "/analyze",
        json={
            "set_number": lego_set["set_number"],
            "user_goal": "buy",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "asking_price is required for buy analysis."
    assert "missing required asking price" in caplog.text
    assert "error_type=RecommendationValidationError" in caplog.text


def test_analyze_endpoint_allows_sell_without_asking_price(client: TestClient):
    lego_set = create_lego_set(client)
    client.post("/snapshots", json=create_snapshot_payload(lego_set["set_number"]))

    response = client.post(
        "/analyze",
        json={
            "set_number": lego_set["set_number"],
            "user_goal": "sell",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["recommendation"] == "WATCH"
    assert body["reason_codes"] == [
        "missing_purchase_price",
        "insufficient_trend_data",
        "moderate_market_depth",
    ]
    assert body["cost_basis"] is None
    assert body["profit"] is None


def test_analyze_endpoint_sell_goal_uses_hold_sell_engine(client: TestClient):
    create_lego_set(client, "910023")
    for days_ago, median_price in [(2, "150.00"), (1, "160.00"), (0, "200.00")]:
        snapshot = create_snapshot_payload("910023", fair_value=median_price)
        snapshot.update(
            {
                "marketplace_name": "ebay",
                "condition": "new",
                "low_price": "150.00",
                "median_price": median_price,
                "average_price": median_price,
                "high_price": "210.00",
                "listing_count": 24,
                "snapshot_at": (
                    datetime.now(UTC) - timedelta(days=days_ago)
                ).isoformat(),
            }
        )
        response = client.post("/snapshots", json=snapshot)
        assert response.status_code == 201, response.text

    response = client.post(
        "/analyze",
        json={
            "set_number": "910023",
            "user_goal": "sell",
            "purchase_price": "80.00",
            "quantity": 2,
            "condition": "new",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["recommendation"] == "SELL"
    assert body["score"] == 83
    assert body["estimated_net_sell_value"] == 174.0
    assert body["total_estimated_net_value"] == 348.0
    assert body["cost_basis"] == 160.0
    assert body["profit"] == 188.0
    assert body["profit_pct"] == 117.5
    assert body["trend_label"] == "rising"
    assert body["trend_pct"] == 29.03
    assert "very_strong_profit" in body["reason_codes"]
    assert "price_trend_rising" in body["reason_codes"]


def test_post_analyze_returns_low_confidence_result_when_no_snapshots_exist(
    client: TestClient,
):
    lego_set = create_lego_set(client)

    response = client.post(
        "/analyze",
        json={
            "set_number": lego_set["set_number"],
            "user_goal": "buy",
            "asking_price": "100.00",
        },
    )

    logger.info(
        f"API TEST: POST /analyze no snapshot explicit status={response.status_code}"
    )
    assert response.status_code == 201
    body = response.json()
    assert body["recommendation"] == "WATCH"
    assert body["confidence"] == "low"
    assert body["score"] == 40


def test_post_analyze_saves_recommendation_to_db(client: TestClient):
    lego_set = create_lego_set(client)
    snapshot_payload = create_snapshot_payload(lego_set["set_number"])
    snapshot_payload.update({"median_price": "200.00", "listing_count": 24})
    client.post("/snapshots", json=snapshot_payload)

    analyzed = client.post(
        "/analyze",
        json={
            "set_number": lego_set["set_number"],
            "user_goal": "buy",
            "asking_price": "160.00",
        },
    ).json()
    response = client.get(f"/recommendation/{lego_set['set_number']}")

    logger.info(f"API TEST: GET saved recommendation status={response.status_code}")
    assert response.status_code == 200
    saved = response.json()
    assert saved["set_number"] == analyzed["set_number"]
    assert saved["recommendation"] == analyzed["recommendation"]
    assert saved["asking_price"] == "160.00"
    assert saved["fair_value"] == 200
    assert saved["reason"] == analyzed["reasoning"]
    assert saved["market_summary"]["set_number"] == lego_set["set_number"]
    assert saved["market_summary"]["recommendation"] == "BUY"
    assert saved["market_summary"]["reason_codes"] == [
        "excellent_discount",
        "high_confidence_data",
        "strong_market_depth",
    ]


def test_analyze_endpoint_calls_engine_pipeline_in_order(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    lego_set = create_lego_set(client)
    client.post("/snapshots", json=create_snapshot_payload(lego_set["set_number"]))
    calls = []

    def estimate_fair_value(snapshots):
        calls.append("price_estimator")
        assert len(snapshots) == 1
        return {
            "fair_value": Decimal("152.00"),
            "market_low": Decimal("120.00"),
            "market_high": Decimal("190.00"),
            "median_price": Decimal("150.00"),
            "listing_count": 12,
            "confidence": "medium",
        }

    def decide_buy_or_pass(**kwargs):
        calls.append("buy_decision_engine")
        assert kwargs["set_number"] == lego_set["set_number"]
        assert kwargs["asking_price"] == 125.00
        assert kwargs["fair_value"] == 152.00
        assert kwargs["market_low"] == 120.00
        assert kwargs["market_high"] == 190.00
        assert kwargs["listing_count"] == 12
        assert kwargs["confidence"] == "medium"
        return {
            "verdict": "BUY",
            "score": 87,
            "confidence": "medium",
            "reasoning": "Buy/pass engine reasoning.",
            "reason_codes": ["strong_discount"],
            "all_in_price": 125.00,
            "fair_value": 152.00,
            "discount_pct": 17.76,
            "estimated_profit": 7.24,
            "estimated_roi_pct": 5.79,
            "target_buy_price": 129.20,
        }

    monkeypatch.setattr(price_estimator, "estimate_fair_value", estimate_fair_value)
    monkeypatch.setattr(
        recommendation_service.buy_decision_engine,
        "decide_buy_or_pass",
        decide_buy_or_pass,
    )

    response = client.post(
        "/analyze",
        json={
            "set_number": lego_set["set_number"],
            "user_goal": "buy",
            "asking_price": "125.00",
        },
    )

    logger.info(f"API TEST: POST /analyze pipeline status={response.status_code}")
    assert response.status_code == 201
    assert calls == ["price_estimator", "buy_decision_engine"]


def test_get_recommendation_endpoint(client: TestClient):
    lego_set = create_lego_set(client)
    client.post("/snapshots", json=create_snapshot_payload(lego_set["set_number"]))
    analyzed = client.post(
        "/analyze",
        json={
            "set_number": int(lego_set["set_number"]),
            "user_goal": "buy_vs_pass",
            "asking_price": "125.00",
        },
    ).json()
    response = client.get(f"/recommendation/{lego_set['set_number']}")

    logger.info(
        f"API TEST: GET /recommendation/{{set_number}} status={response.status_code}"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["set_number"] == analyzed["set_number"]
    assert body["recommendation"] == analyzed["recommendation"]
    assert body["reason"] == analyzed["reasoning"]
