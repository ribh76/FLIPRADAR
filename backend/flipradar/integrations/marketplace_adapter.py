from abc import ABC, abstractmethod
from typing import Any


class MarketplaceAdapter(ABC):
    """Provider boundary for retrieving raw marketplace listings.

    Adapters do not require credentials themselves; configured API clients can be
    introduced behind this interface later without changing marketplace ingestion.
    """

    marketplace: str
    # Mock adapters must opt in explicitly.  The marketplace registry uses
    # this marker to keep fixture data out of non-local environments.
    is_mock_provider: bool = False

    @abstractmethod
    def fetch_listings(self, set_number: str) -> list[dict[str, Any]]:
        """Return provider-tagged raw listings for one LEGO set number."""

    def _tag_marketplace(self, listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{**listing, "marketplace": self.marketplace} for listing in listings]
