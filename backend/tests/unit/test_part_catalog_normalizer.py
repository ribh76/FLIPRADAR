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
