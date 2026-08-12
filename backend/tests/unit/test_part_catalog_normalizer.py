from datetime import UTC, datetime

import pytest

from flipradar.services.errors import ServiceIncompleteDataError
from flipradar.services.part_catalog_normalizer import normalize_part_catalog_record


def test_normalizer_preserves_provider_ids_variants_and_source_metadata():
    record = normalize_part_catalog_record(
        {
            "source": {
                "name": "Provider catalog",
                "url": "https://example.test/catalog",
            },
            "category": {"id": "26", "name": "Bricks"},
            "color": {"id": 5, "name": "Red"},
            "part": {
                "part_num": "3001",
                "name": "Brick 2 x 4",
                "aliases": ["2x4 brick", "2x4 brick"],
                "variants": [{"identifier": "3001a"}],
                "image_url": "https://example.test/3001.png",
                "known_year_range": {"first": "1958", "last": 2026},
            },
            "element": {"element_id": "300121", "name": "Brick 2 x 4 Red"},
        },
        provider="bricklink",
    )

    assert record.part["canonical_identifier"] == "part:3001"
    assert record.part["provider_identifiers"] == {"bricklink": "3001"}
    assert record.part["aliases"] == ["2x4 brick"]
    assert record.part["mold_variants"] == [{"identifier": "3001a"}]
    assert record.part["first_known_year"] == 1958
    assert record.part["last_known_year"] == 2026
    assert record.part["source_name"] == "Provider catalog"


def test_normalizer_does_not_double_prefix_canonical_identifiers_and_normalizes_time():
    record = normalize_part_catalog_record(
        {
            "source": {"updated_at": "2026-08-12T10:00:00"},
            "category": {"canonical_identifier": "category:26", "name": "Bricks"},
            "color": {"canonical_identifier": "color:5", "name": "Red"},
            "part": {"canonical_identifier": "part:3001", "name": "Brick 2 x 4"},
            "element": {
                "canonical_identifier": "element:300121",
                "name": "Brick 2 x 4 Red",
            },
        },
        provider="bricklink",
    )

    assert record.part["canonical_identifier"] == "part:3001"
    assert record.element["canonical_identifier"] == "element:300121"
    assert record.part["source_updated_at"] == datetime(2026, 8, 12, 10, tzinfo=UTC)
    assert {"missing_aliases", "missing_images", "missing_known_year_range"} <= set(
        record.part["quality_flags"]
    )
    assert "source_timestamp_missing" not in record.part["quality_flags"]


@pytest.mark.parametrize(
    "record",
    [
        {"source": "not-an-object"},
        {
            "category": {"part_num": "3001", "name": "Bricks"},
            "color": {"id": "5", "name": "Red"},
            "part": {"part_num": "3001", "name": "Brick"},
            "element": {"element_id": "300121", "name": "Brick Red"},
        },
        {
            "category": {"id": "26", "name": "Bricks"},
            "color": {"id": "5", "name": "Red"},
            "part": {"part_num": "3001", "name": "Brick", "aliases": {"bad": "shape"}},
            "element": {"element_id": "300121", "name": "Brick Red"},
        },
    ],
)
def test_normalizer_rejects_malformed_provider_shapes(record):
    with pytest.raises(ServiceIncompleteDataError):
        normalize_part_catalog_record(record, provider="bricklink")
