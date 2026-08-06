import pytest

from flipradar.services.errors import ServiceValidationError
from flipradar.services.listing_url_ingestion import (
    normalize_listing_url,
    resolve_shortened_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://www.ebay.com/itm/123456789012",
        "https://127.0.0.1/itm/123456789012",
        "https://[::1]/itm/123456789012",
        "https://ebay.com.evil.test/itm/123456789012",
        "https://www.bricklink.com@evil.test/v2/catalog/catalogitem.page#O=123",
        "https://www.example.com/itm/123456789012",
        "https://www.ebay.com/search?q=lego",
    ],
)
def test_normalize_listing_url_rejects_malicious_or_unsupported_urls(url):
    with pytest.raises(ServiceValidationError):
        normalize_listing_url(url)


def test_normalize_listing_url_normalizes_mobile_regional_tracking_url():
    target = normalize_listing_url(
        "https://m.ebay.co.uk/itm/LEGO-set/123456789012?campid=tracking"
    )
    assert target.provider == "ebay"
    assert target.external_listing_id == "123456789012"
    assert target.url == "https://www.ebay.com/itm/123456789012"


def test_normalize_listing_url_extracts_bricklink_inventory_from_fragment():
    target = normalize_listing_url(
        "https://www.bricklink.com/v2/catalog/catalogitem.page?S=75192#T=S&O=7654321"
    )
    assert target.provider == "bricklink"
    assert target.external_listing_id == "7654321"


def test_short_url_redirect_to_private_address_is_rejected_without_following_it(
    monkeypatch,
):
    class Response:
        is_redirect = True
        headers = {"Location": "https://127.0.0.1/itm/123456789012"}

    monkeypatch.setattr("requests.head", lambda *args, **kwargs: Response())
    with pytest.raises(ServiceValidationError):
        resolve_shortened_url("https://ebay.to/abc", timeout_seconds=1)
