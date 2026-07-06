from random import randint
from uuid import uuid4

from app.schemas.validation import normalize_set_number


def fetch(set_number: str) -> list[dict]:
    """Return fake eBay listings until the real API integration is available."""
    normalized_set_number = normalize_set_number(set_number)
    listing_count = randint(5, 25)
    listings = []
    conditions = ["New", "Used", "Pre-Owned"]

    for index in range(listing_count):
        price = randint(35, 350)
        shipping = randint(0, 30)
        condition = conditions[randint(0, len(conditions) - 1)]
        listing_id = f"ebay-{normalized_set_number}-{uuid4().hex[:12]}"
        listings.append(
            {
                "id": listing_id,
                "price": price,
                "shipping": shipping,
                "condition": condition,
                "title": f"LEGO {normalized_set_number} {condition} marketplace listing {index + 1}",
                "listing_url": f"https://www.ebay.com/itm/{listing_id}",
                "seller": f"ebay-seller-{randint(100, 999)}",
                "currency": "USD",
            }
        )

    return listings
