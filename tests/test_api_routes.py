import logging
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import models  # noqa: F401
from app.main import app
from database import Base, get_db_session
from engine import decision_engine, price_estimator, scoring_engine

logger = logging.getLogger(__name__)


@pytest.fixture
def client():
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
    return {
        "set_number": set_number,
        "marketplace_name": "ebay",
        "condition": "new",
        "currency": "USD",
        "low_price": "120.00",
        "median_price": "150.00",
        "average_price": "151.25",
        "high_price": "190.00",
        "fair_market_value": fair_value,
        "listing_count": 12,
        "source_payload": {"source": "pytest-api"},
    }


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


def test_list_sets_endpoint(client: TestClient):
    lego_set = create_lego_set(client)
    response = client.get("/sets")

    logger.info(f"API TEST: GET /sets status={response.status_code}")
    assert response.status_code == 200
    assert any(item["set_number"] == lego_set["set_number"] for item in response.json())


def test_create_listing_endpoint(client: TestClient):
    lego_set = create_lego_set(client)
    payload = create_listing_payload(lego_set["set_number"])
    response = client.post("/listings", json=payload)

    logger.info(f"API TEST: POST /listings status={response.status_code}")
    assert response.status_code == 201
    assert response.json()["external_listing_id"] == payload["external_listing_id"]


def test_listings_by_set_endpoint(client: TestClient):
    lego_set = create_lego_set(client)
    listing = client.post(
        "/listings", json=create_listing_payload(lego_set["set_number"])
    ).json()
    response = client.get(f"/listings/{lego_set['set_number']}")

    logger.info(f"API TEST: GET /listings/{{set_number}} status={response.status_code}")
    assert response.status_code == 200
    assert any(item["id"] == listing["id"] for item in response.json())


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
    assert any(item["id"] == listing["id"] for item in response.json())


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
    assert any(item["id"] == snapshot["id"] for item in response.json())


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


def auth_headers(client: TestClient, username: str | None = None) -> dict:
    resolved_username = username or f"user-{uuid4().hex[:8]}"
    response = client.post(
        "/auth/register",
        json={
            "username": resolved_username,
            "email": f"{resolved_username}@example.com",
            "password": "correct-horse-battery",
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_register_success(client: TestClient):
    response = client.post(
        "/auth/register",
        json={
            "username": "collector",
            "email": "collector@example.com",
            "password": "correct-horse-battery",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == "collector"


def test_duplicate_register_fails(client: TestClient):
    payload = {
        "username": "duplicate",
        "email": "duplicate@example.com",
        "password": "correct-horse-battery",
    }
    assert client.post("/auth/register", json=payload).status_code == 201
    response = client.post("/auth/register", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "User already exists"


def test_login_success(client: TestClient):
    client.post(
        "/auth/register",
        json={
            "username": "loginuser",
            "email": "loginuser@example.com",
            "password": "correct-horse-battery",
        },
    )
    response = client.post(
        "/auth/login",
        json={
            "username_or_email": "loginuser",
            "password": "correct-horse-battery",
        },
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_bad_password_fails(client: TestClient):
    client.post(
        "/auth/register",
        json={
            "username": "badlogin",
            "email": "badlogin@example.com",
            "password": "correct-horse-battery",
        },
    )
    response = client.post(
        "/auth/login",
        json={"username_or_email": "badlogin", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_auth_me_works_with_token(client: TestClient):
    headers = auth_headers(client, "profileuser")
    response = client.get("/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["username"] == "profileuser"


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
    assert len(list_response.json()) == 1

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
    assert client.get("/portfolio", headers=headers).json() == []


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
    assert summary["holdings"][0]["valuation_status"] == "missing_market_data"


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
    assert body["market_high"] == "190.00"
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
    assert body["score"] == 82
    assert body["confidence"] == "medium"
    assert (
        body["reasoning"]
        == "Asking price is 16.7% below estimated market value; deal strength is strong."
    )


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
    assert body["score"] == 90
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
    assert body["score"] == 50
    assert body["confidence"] == "high"
    assert body["reasoning"] == "Asking price margin is -20.0%; deal strength is bad."


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
    assert body == {
        "set_number": "75192",
        "user_goal": "buy",
        "asking_price": 550.0,
        "fair_value": 625.0,
        "score": 82,
        "recommendation": "BUY",
        "confidence": "high",
        "reasoning": (
            "Asking price is 12.0% below estimated market value; "
            "deal strength is strong."
        ),
        "market_low": 590.0,
        "market_high": 700.0,
        "listing_count": 22,
    }


def test_analyze_endpoint_returns_404_for_missing_set(client: TestClient):
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


def test_analyze_endpoint_without_snapshots_returns_low_confidence(client: TestClient):
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
    assert body["score"] == 25
    assert body["recommendation"] == "WATCH"
    assert body["confidence"] == "low"
    assert body["reasoning"] == "No price snapshots found for this set."


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
    assert body["score"] == 25


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

    def score_recommendation(asking_price, fair_value, confidence, listing_count):
        calls.append("scoring_engine")
        assert asking_price == Decimal("125.00")
        assert fair_value == Decimal("152.00")
        assert confidence == "medium"
        assert listing_count == 12
        return {
            "score": 87,
            "margin_percent": Decimal("17.8"),
            "deal_band": "strong",
        }

    def decide(score_result, user_goal, asking_price, fair_value, *, has_snapshots):
        calls.append("decision_engine")
        assert score_result["score"] == 87
        assert user_goal == "buy"
        assert asking_price == Decimal("125.00")
        assert fair_value == Decimal("152.00")
        assert has_snapshots is True
        return decision_engine.DecisionResult(
            recommendation=decision_engine.RecommendationDecision.BUY,
            reasoning="Asking price is 17.8% below estimated market value.",
        )

    monkeypatch.setattr(price_estimator, "estimate_fair_value", estimate_fair_value)
    monkeypatch.setattr(scoring_engine, "score_recommendation", score_recommendation)
    monkeypatch.setattr(decision_engine, "decide", decide)

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
    assert calls == ["price_estimator", "scoring_engine", "decision_engine"]


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
