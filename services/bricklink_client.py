from datetime import UTC, datetime
from decimal import Decimal
from random import randint
from uuid import NAMESPACE_URL, uuid4, uuid5


class MockBricklinkSetNotFoundError(LookupError):
    """Raised when a set is not present in the local BrickLink mock catalog."""


MOCK_SET_DETAILS: dict[str, dict] = {
    "75192": {
        "set_number": "75192",
        "name": "Millennium Falcon",
        "theme": "Star Wars",
        "subtheme": "Ultimate Collector Series",
        "release_year": 2017,
        "retirement_year": None,
        "piece_count": 7541,
        "minifig_count": 8,
        "low_price": Decimal("610.00"),
        "median_price": Decimal("720.00"),
        "average_price": Decimal("735.50"),
        "high_price": Decimal("880.00"),
        "fair_market_value": Decimal("725.00"),
        "listing_count": 18,
    },
    "10305": {
        "set_number": "10305",
        "name": "Lion Knights' Castle",
        "theme": "Icons",
        "subtheme": "Castle",
        "release_year": 2022,
        "retirement_year": None,
        "piece_count": 4514,
        "minifig_count": 22,
        "low_price": Decimal("340.00"),
        "median_price": Decimal("385.00"),
        "average_price": Decimal("392.25"),
        "high_price": Decimal("475.00"),
        "fair_market_value": Decimal("389.00"),
        "listing_count": 14,
    },
    "21325": {
        "set_number": "21325",
        "name": "Medieval Blacksmith",
        "theme": "Ideas",
        "subtheme": "Castle",
        "release_year": 2021,
        "retirement_year": 2023,
        "piece_count": 2164,
        "minifig_count": 4,
        "low_price": Decimal("205.00"),
        "median_price": Decimal("245.00"),
        "average_price": Decimal("251.20"),
        "high_price": Decimal("320.00"),
        "fair_market_value": Decimal("248.00"),
        "listing_count": 11,
    },
}


def fetch_set_metadata(set_number: str) -> dict:
    """Return deterministic mock set metadata until BrickLink API is configured."""
    mock_set = MOCK_SET_DETAILS.get(str(set_number))
    if mock_set is None:
        raise MockBricklinkSetNotFoundError(
            f"BrickLink mock set not found: {set_number}"
        )

    metadata_fields = (
        "set_number",
        "name",
        "theme",
        "subtheme",
        "release_year",
        "retirement_year",
        "piece_count",
        "minifig_count",
    )
    return {field: mock_set[field] for field in metadata_fields}


def fetch_set_price_snapshot(set_number: str) -> dict:
    """Return a deterministic mock latest valuation snapshot for a BrickLink set."""
    mock_set = MOCK_SET_DETAILS.get(str(set_number))
    if mock_set is None:
        raise MockBricklinkSetNotFoundError(
            f"BrickLink mock set not found: {set_number}"
        )

    snapshot_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    return {
        "id": uuid5(NAMESPACE_URL, f"bricklink-mock-snapshot:{set_number}"),
        "condition": "new",
        "currency": "USD",
        "low_price": mock_set["low_price"],
        "median_price": mock_set["median_price"],
        "average_price": mock_set["average_price"],
        "high_price": mock_set["high_price"],
        "fair_market_value": mock_set["fair_market_value"],
        "listing_count": mock_set["listing_count"],
        "snapshot_at": snapshot_at,
        "created_at": snapshot_at,
    }


def fetch(set_number: str) -> list[dict]:
    """Return fake BrickLink listings until the real API integration is available."""
    listing_count = randint(5, 25)
    listings = []
    conditions = ["N", "U"]

    for index in range(listing_count):
        price = randint(30, 325)
        shipping_price = randint(0, 24)
        condition = conditions[randint(0, len(conditions) - 1)]
        listing_id = f"bricklink-{set_number}-{uuid4().hex[:12]}"
        listings.append(
            {
                "listing_id": listing_id,
                "unit_price": price,
                "shipping_price": shipping_price,
                "condition": condition,
                "item_name": f"LEGO {set_number} BrickLink lot {index + 1}",
                "url": f"https://www.bricklink.com/v2/catalog/catalogitem.page?S={set_number}#T=S&O={listing_id}",
                "seller_name": f"bricklink-store-{randint(100, 999)}",
                "currency_code": "USD",
            }
        )

    return listings
