from flipradar.domain.models import Color, Element, Part, PartCategory


def test_part_catalog_models_expose_provider_metadata_and_available_colors():
    category = PartCategory(provider_identifiers={"bricklink": "26"}, name="Bricks")
    color = Color(provider_identifiers={"bricklink": "5"}, name="Red")
    part = Part(
        provider_identifiers={"bricklink": "3001"},
        name="Brick 2 x 4",
        category=category,
        aliases=["2x4 brick"],
        mold_variants=[{"provider_identifier": "3001a"}],
        image_urls=["https://example.test/3001.png"],
        first_known_year=1958,
        last_known_year=2026,
    )
    element = Element(
        provider_identifiers={"lego": "300121"},
        name="Red Brick 2 x 4",
        part=part,
        color=color,
        first_known_year=1958,
        last_known_year=2026,
    )

    assert part.category is category
    assert part.elements == [element]
    assert list(part.available_colors) == [color]
    assert element.part is part
    assert element.color is color
