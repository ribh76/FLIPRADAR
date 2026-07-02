from random import randint
from uuid import uuid4


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
