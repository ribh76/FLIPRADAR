import pytest

from flipradar.services.errors import ServiceValidationError
from flipradar.services.saved_search_service import (
    migrate_filter_config,
    validate_filter_config,
)


def test_saved_search_filter_migration_upgrades_legacy_min_price():
    version, config = migrate_filter_config(0, {"min_price": 120, "theme": "Icons"})

    assert version == 1
    assert config == {"min_budget": 120, "theme": "Icons"}


def test_saved_search_configuration_rejects_unknown_and_invalid_filters():
    with pytest.raises(ServiceValidationError, match="Unsupported deal filters"):
        validate_filter_config({"unsupported": "value"})
    with pytest.raises(ServiceValidationError, match="minimum budget"):
        validate_filter_config({"min_budget": 500, "max_budget": 100})


def test_saved_search_configuration_retains_only_supported_filters():
    config = validate_filter_config({"theme": "Star Wars", "order": "discount_desc"})

    assert config == {"theme": "Star Wars", "order": "discount_desc"}
