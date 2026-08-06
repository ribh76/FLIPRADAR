import pytest

from flipradar.core.settings import ProviderSettings
from flipradar.integrations.listing_provider_client import (
    OfficialListingProviderClient,
    ProviderRetrievalError,
)


def test_ebay_provider_rejects_malformed_provider_response(monkeypatch):
    class Response:
        status_code = 200

        def json(self):
            return ["not", "an", "object"]

    monkeypatch.setattr("requests.post", lambda *args, **kwargs: Response())
    settings = ProviderSettings(
        enabled=True,
        configured=True,
        timeout_seconds=1,
        api_key="key",
        api_secret="secret",
    )

    with pytest.raises(ProviderRetrievalError, match="invalid response"):
        OfficialListingProviderClient().fetch(
            "ebay", "123456789012", "https://www.ebay.com/itm/123456789012", settings
        )
