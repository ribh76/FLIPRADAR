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
from flipradar.database import Base, get_db_session
from flipradar.domain.engines import price_estimator
from flipradar.domain.models import User
from flipradar.main import create_app
from flipradar.services import auth_service, recommendation_service

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


def test_create_listing_endpoint(client: TestClient):
    lego_set = create_lego_set(client)
    payload = create_listing_payload(lego_set["set_number"])
    response = client.post("/listings", json=payload)

    logger.info(f"API TEST: POST /listings status={response.status_code}")
    assert response.status_code == 201
    assert response.json()["external_listing_id"] == payload["external_listing_id"]


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
    assert any(item["id"] == listing["id"] for item in collection_data(response))


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


def verification_token_from_url(verification_url: str) -> str:
    parsed = urlparse(verification_url)
    tokens = parse_qs(parsed.query).get("token")
    assert tokens, verification_url
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
    assert body["is_email_verified"] is False
    assert "hashed_password" not in body


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
