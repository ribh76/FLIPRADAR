import json
from dataclasses import dataclass
from pathlib import Path

from flipradar.services.marketplace_service import _listings_for_automated_pricing
from flipradar.services.product_matching_engine import (
    AUTOMATED_PRICING_MIN_CONFIDENCE,
    detect_listing_exclusions,
    extract_candidate_set_numbers,
    find_catalog_match,
    match_listing_to_set,
    normalize_title,
    title_keywords,
)


def test_normalizes_titles_and_extracts_product_keywords():
    assert (
        normalize_title(" LEGO® Star-Wars™: The Falcon! ")
        == "lego star wars the falcon"
    )
    assert title_keywords("LEGO Star Wars The Falcon - New Sealed") == (
        "star",
        "wars",
        "falcon",
    )


def test_extracts_labelled_and_unlabelled_set_number_candidates_once():
    assert extract_candidate_set_numbers("LEGO Set # 75192-1 / item 10305, 75313") == (
        "75192-1",
        "10305",
        "75313",
    )


def test_does_not_treat_piece_counts_as_second_set_identifiers():
    assert extract_candidate_set_numbers("LEGO 75192, 7541 pieces, released 2017") == (
        "75192",
    )


def test_rejects_two_identifiers_when_title_is_ambiguous():
    result = match_listing_to_set(
        "LEGO 75192 and 75257 collection",
        set_number="75192",
        set_name="Millennium Falcon",
    )

    assert result.is_match is False
    assert result.confidence == 0
    assert "multi_set_lot" in result.exclusion_reasons


def test_exact_set_number_match_is_authoritative_even_when_name_tokens_differ():
    result = match_listing_to_set(
        "LEGO 75192 sealed collector edition",
        set_number="75192",
        set_name="Millennium Falcon",
    )

    assert result.is_match is True
    assert result.detected_set_number == "75192"
    assert result.confidence == 100
    assert result.match_reasons == ("exact_set_number",)
    assert result.is_eligible_for_automated_pricing is True
    assert result.explanation == "exact_set_number (confidence=100)"


def test_different_detected_set_number_rejects_similar_set_name():
    result = match_listing_to_set(
        "LEGO Millennium Falcon 75257 brand new",
        set_number="75192",
        set_name="Millennium Falcon",
    )

    assert result.is_match is False
    assert result.confidence == 0


def test_set_number_version_suffix_is_not_treated_as_an_exact_match():
    result = match_listing_to_set(
        "LEGO 75192-1 sealed",
        set_number="75192",
        set_name="Millennium Falcon",
    )

    assert result.is_match is False
    assert result.candidate_set_numbers == ("75192-1",)


def test_name_tokens_are_a_conservative_fallback_when_no_number_is_present():
    result = match_listing_to_set(
        "LEGO Lion Knights Castle sealed",
        set_number="10305",
        set_name="Lion Knights' Castle",
    )

    assert result.is_match is True
    assert result.detected_set_number is None
    assert result.confidence == 80
    assert result.match_reasons == (
        "set_name_token_match",
        "set_name_token_coverage:3/3",
    )
    assert result.is_eligible_for_automated_pricing is False
    assert AUTOMATED_PRICING_MIN_CONFIDENCE == 90


def test_excluded_listing_types_are_rejected_even_with_an_exact_set_number():
    cases = {
        "LEGO 75192 instructions only": "instructions_only",
        "LEGO 75192 empty box only": "box_only",
        "LEGO 75192 minifigures lot": "minifigures_only",
        "LEGO 75192 parts lot": "parts_only",
        "LEGO 75192 MOC custom build": "custom_build",
        "Counterfeit LEGO 75192 clone": "counterfeit_or_non_lego",
    }

    for title, reason in cases.items():
        result = match_listing_to_set(
            title, set_number="75192", set_name="Millennium Falcon"
        )
        assert result.is_match is False
        assert result.confidence == 0
        assert reason in result.exclusion_reasons


def test_multi_set_lots_are_rejected_at_zero_confidence():
    title = "LEGO set lot 75192 and 75257, sealed"
    result = match_listing_to_set(
        title, set_number="75192", set_name="Millennium Falcon"
    )

    assert detect_listing_exclusions(title) == ("multi_set_lot",)
    assert result.is_match is False
    assert result.confidence == 0
    assert result.exclusion_reasons == ("multi_set_lot",)


@dataclass
class CatalogSet:
    set_number: str
    name: str


def test_catalog_matching_does_not_choose_an_ambiguous_name_match():
    catalog = [
        CatalogSet("75192", "Millennium Falcon"),
        CatalogSet("75257", "Millennium Falcon"),
    ]

    assert find_catalog_match("LEGO Millennium Falcon sealed", catalog) is None
    match = find_catalog_match("LEGO 75257 sealed", catalog)
    assert match is not None
    # assert match[0].set_number == "75257"


def test_automated_pricing_uses_only_listings_at_or_above_match_threshold():
    listings = [
        {"external_listing_id": "exact", "match_confidence": 100},
        {"external_listing_id": "title-only", "match_confidence": 80},
        {"external_listing_id": "unmatched", "match_confidence": 0},
    ]

    assert _listings_for_automated_pricing(listings) == [listings[0]]


def test_labeled_product_matching_dataset_covers_expected_decisions():
    fixture_path = (
        Path(__file__).parents[1] / "fixtures" / "product_matching_cases.json"
    )
    cases = json.loads(fixture_path.read_text())

    assert len(cases) >= 10
    for case in cases:
        result = match_listing_to_set(
            case["title"],
            set_number=case["set_number"],
            set_name=case["set_name"],
        )
        assert result.is_match is case["expected_match"], case["id"]
        assert result.confidence == case["expected_confidence"], case["id"]
        for reason in case["expected_reasons"]:
            assert (
                reason in result.match_reasons or reason in result.exclusion_reasons
            ), case["id"]


def test_explanation_identifies_rejection_and_flags_for_developer_debugging():
    result = match_listing_to_set(
        "Counterfeit LEGO 75192 clone",
        set_number="75192",
        set_name="Millennium Falcon",
    )

    assert result.explanation == "rejected: counterfeit_or_non_lego"
