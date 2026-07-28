"""Conservative matching of marketplace listing titles to LEGO catalog sets.

Set numbers are the authoritative signal.  Name matching is intentionally only
used when a listing title contains no plausible set-number candidate at all.
This prevents a title such as "Millennium Falcon 75257" from being associated
with the UCS Millennium Falcon (75192) merely because the names overlap.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from flipradar.api.schemas.validation import normalize_set_number

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_LABELLED_SET_NUMBER_PATTERN = re.compile(
    r"(?<![a-z0-9])(?:lego\s*)?(?:set|model|item|#)\s*[:#-]?\s*"
    r"(\d{3,8}(?:-\d{1,3})?)(?![a-z0-9])",
    re.IGNORECASE,
)
_UNLABELLED_SET_NUMBER_PATTERN = re.compile(
    r"(?<![a-z0-9])(\d{4,8}(?:-\d{1,3})?)(?![a-z0-9])", re.IGNORECASE
)
_NON_PRODUCT_KEYWORDS = frozenset(
    {
        "a",
        "and",
        "brand",
        "box",
        "complete",
        "for",
        "in",
        "lego",
        "lot",
        "new",
        "of",
        "open",
        "preowned",
        "pre",
        "sealed",
        "set",
        "the",
        "used",
        "with",
    }
)
_MIN_NAME_TOKEN_OVERLAP = 2
_MIN_NAME_TOKEN_COVERAGE = 0.75
_EXCLUSION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instructions_only",
        re.compile(
            r"\b(?:instructions?|manual|building guide)\b.*\b(?:only|just)\b"
        ),
    ),
    (
        "box_only",
        re.compile(r"\b(?:empty |original )?box\b.*\b(?:only|no set|no lego)\b"),
    ),
    (
        "minifigures_only",
        re.compile(r"\b(?:minifig(?:ure)?s?|minifigs|figs?)\b\s+(?:only|lot|bundle)\b"),
    ),
    (
        "parts_only",
        re.compile(r"\b(?:parts?|pieces?|bricks?)\b\s+(?:only|lot|bundle)\b"),
    ),
    (
        "custom_build",
        re.compile(r"\b(?:moc|custom (?:build|model|creation)|my own creation)\b"),
    ),
    (
        "counterfeit_or_non_lego",
        re.compile(
            r"\b(?:counterfeit|fake|bootleg|knockoff|clone|lepin|non lego|not lego|"
            r"lego compatible|compatible with lego)\b"
        ),
    ),
)
_MULTI_SET_TERMS_PATTERN = re.compile(
    r"\b(?:lot|bundle|collection|multiple|multi set|sets)\b"
)
_MULTI_SET_CONNECTOR_PATTERN = re.compile(r"\d{4,8}(?:-\d{1,3})?\s*(?:and|&|\+|/)\s*\d{4,8}")


@dataclass(frozen=True)
class ProductMatch:
    """The explainable outcome of matching one listing to one catalog set."""

    is_match: bool
    confidence: int
    detected_set_number: str | None
    candidate_set_numbers: tuple[str, ...]
    title_keywords: tuple[str, ...]
    set_name_keywords: tuple[str, ...]
    matching_keywords: tuple[str, ...]
    exclusion_reasons: tuple[str, ...] = ()


def normalize_title(title: object) -> str:
    """Return a lowercase, punctuation- and accent-insensitive title string."""
    ascii_text = _ascii_lower(title)
    return " ".join(_TOKEN_PATTERN.findall(ascii_text.lower()))


def title_keywords(title: object) -> tuple[str, ...]:
    """Extract meaningful comparison keywords from a title or set name."""
    return tuple(
        token
        for token in normalize_title(title).split()
        if not token.isdigit() and token not in _NON_PRODUCT_KEYWORDS
    )


def extract_candidate_set_numbers(title: object) -> tuple[str, ...]:
    """Extract de-duplicated LEGO set-number candidates from listing text.

    Explicit labels can identify older three-digit sets; unlabeled values require
    four digits to avoid treating listing quantities as set identifiers.
    """
    normalized = _ascii_lower(title)
    candidates: list[str] = []
    for pattern in (_LABELLED_SET_NUMBER_PATTERN, _UNLABELLED_SET_NUMBER_PATTERN):
        for match in pattern.finditer(normalized):
            candidate = normalize_set_number(match.group(1))
            if candidate not in candidates:
                candidates.append(candidate)
    return tuple(candidates)


def _ascii_lower(value: object) -> str:
    original_text = str(value or "")
    text = unicodedata.normalize(
        "NFKD",
        "".join(
            character
            for character in original_text
            if not unicodedata.category(character).startswith("S")
        ),
    )
    text_without_symbols = "".join(
        character
        for character in text
        if not unicodedata.category(character).startswith("S")
    )
    return text_without_symbols.encode("ascii", "ignore").decode("ascii").lower()


def _contains_exact_set_number(title: object, set_number: str) -> bool:
    """Check a catalog identifier verbatim, including non-numeric legacy IDs."""
    normalized_title = _ascii_lower(title)
    normalized_number = _ascii_lower(set_number)
    return bool(
        re.search(
            rf"(?<![a-z0-9]){re.escape(normalized_number)}(?![a-z0-9]|-\d)",
            normalized_title,
        )
    )


def detect_listing_exclusions(
    listing_title: object, candidate_set_numbers: tuple[str, ...] | None = None
) -> tuple[str, ...]:
    """Return reasons a title is not an offer for one complete official set."""
    normalized_title = normalize_title(listing_title)
    candidates = candidate_set_numbers or extract_candidate_set_numbers(listing_title)
    reasons = [
        reason
        for reason, pattern in _EXCLUSION_PATTERNS
        if pattern.search(normalized_title)
    ]
    is_multi_set_lot = len(candidates) > 1 and (
        _MULTI_SET_TERMS_PATTERN.search(normalized_title)
        or _MULTI_SET_CONNECTOR_PATTERN.search(_ascii_lower(listing_title))
    )
    if is_multi_set_lot:
        reasons.append("multi_set_lot")
    return tuple(reasons)


def match_listing_to_set(
    listing_title: object, *, set_number: str, set_name: object
) -> ProductMatch:
    """Match a listing title to one catalog set.

    Disallowed listing types always receive 0 confidence. A detected exact set
    number otherwise wins with 100 confidence. Any detected number that differs
    from the requested set is a definitive non-match. Only titles without number
    candidates may use name token comparison as a fallback.
    """
    canonical_set_number = normalize_set_number(set_number)
    candidates = extract_candidate_set_numbers(listing_title)
    listing_keywords = title_keywords(listing_title)
    name_keywords = title_keywords(set_name)
    matching_keywords = tuple(sorted(set(listing_keywords) & set(name_keywords)))
    exclusion_reasons = detect_listing_exclusions(listing_title, candidates)
    detected_set_number = (
        canonical_set_number
        if _contains_exact_set_number(listing_title, canonical_set_number)
        else None
    )

    if exclusion_reasons:
        return ProductMatch(
            is_match=False,
            confidence=0,
            detected_set_number=detected_set_number,
            candidate_set_numbers=candidates,
            title_keywords=listing_keywords,
            set_name_keywords=name_keywords,
            matching_keywords=matching_keywords,
            exclusion_reasons=exclusion_reasons,
        )

    if detected_set_number:
        return ProductMatch(
            is_match=True,
            confidence=100,
            detected_set_number=canonical_set_number,
            candidate_set_numbers=candidates,
            title_keywords=listing_keywords,
            set_name_keywords=name_keywords,
            matching_keywords=matching_keywords,
        )

    if candidates:
        return ProductMatch(
            is_match=False,
            confidence=0,
            detected_set_number=None,
            candidate_set_numbers=candidates,
            title_keywords=listing_keywords,
            set_name_keywords=name_keywords,
            matching_keywords=matching_keywords,
        )

    name_keyword_set = set(name_keywords)
    matching_keyword_set = set(matching_keywords)
    coverage = len(matching_keyword_set) / len(name_keyword_set) if name_keyword_set else 0
    is_match = (
        len(matching_keyword_set) >= _MIN_NAME_TOKEN_OVERLAP
        and coverage >= _MIN_NAME_TOKEN_COVERAGE
    )
    confidence = round(80 * coverage) if is_match else 0
    return ProductMatch(
        is_match=is_match,
        confidence=confidence,
        detected_set_number=None,
        candidate_set_numbers=candidates,
        title_keywords=listing_keywords,
        set_name_keywords=name_keywords,
        matching_keywords=matching_keywords,
    )


def find_catalog_match(
    listing_title: object, catalog_sets: Iterable[object]
) -> tuple[object, ProductMatch] | None:
    """Find one unambiguous catalog match from objects with number and name fields."""
    matches: list[tuple[object, ProductMatch]] = []
    for lego_set in catalog_sets:
        result = match_listing_to_set(
            listing_title,
            set_number=lego_set.set_number,
            set_name=lego_set.name,
        )
        if result.is_match:
            matches.append((lego_set, result))

    if not matches:
        return None
    exact_matches = [match for match in matches if match[1].detected_set_number]
    candidates = exact_matches or matches
    return candidates[0] if len(candidates) == 1 else None
