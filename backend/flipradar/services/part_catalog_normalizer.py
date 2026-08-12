"""Normalize provider part records into a stable catalog representation."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from flipradar.services.errors import ServiceIncompleteDataError


@dataclass(frozen=True)
class NormalizedPartCatalogRecord:
    category: dict[str, Any]
    color: dict[str, Any]
    part: dict[str, Any]
    element: dict[str, Any]


def normalize_part_catalog_record(
    raw_record: Mapping[str, Any], *, provider: str, fetched_at: datetime | None = None
) -> NormalizedPartCatalogRecord:
    """Coerce a provider record while retaining all known identifiers and variants."""
    provider = provider.strip().lower()
    if not provider:
        raise ServiceIncompleteDataError("Catalog provider is required")
    fetched_at = fetched_at or datetime.now(UTC)
    source = (
        raw_record.get("source")
        if isinstance(raw_record.get("source"), Mapping)
        else {}
    )
    common = {
        "source_name": str(source.get("name") or f"{provider.title()} catalog"),
        "source_url": source.get("url"),
        "source_updated_at": _as_datetime(source.get("updated_at")),
        "fetched_at": fetched_at,
    }
    category = _normalize_entity(
        raw_record.get("category"), "category", provider, common
    )
    color = _normalize_entity(raw_record.get("color"), "color", provider, common)
    part = _normalize_entity(raw_record.get("part"), "part", provider, common)
    element = _normalize_entity(raw_record.get("element"), "element", provider, common)
    return NormalizedPartCatalogRecord(
        category=category, color=color, part=part, element=element
    )


def _normalize_entity(
    raw: Any, kind: str, provider: str, common: Mapping[str, Any]
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ServiceIncompleteDataError(f"Provider record is missing {kind} metadata")
    identifier = _first_text(
        raw.get("canonical_identifier"),
        raw.get("id"),
        raw.get(f"{kind}_id"),
        raw.get("part_num"),
        raw.get("part_number"),
        raw.get("element_id"),
    )
    name = _first_text(raw.get("name"), raw.get("display_name"))
    if not identifier or not name:
        raise ServiceIncompleteDataError(
            f"Provider record has incomplete {kind} metadata"
        )
    raw_identifiers = raw.get("provider_identifiers") or {}
    if not isinstance(raw_identifiers, Mapping):
        raise ServiceIncompleteDataError(
            f"Provider record has invalid {kind} provider identifiers"
        )
    provider_identifiers = {
        str(key).strip().lower(): str(value).strip()
        for key, value in raw_identifiers.items()
        if str(key).strip() and str(value).strip()
    }
    provider_identifiers[provider] = provider_identifiers.get(provider, identifier)
    first_year, last_year = _known_year_range(raw)
    return {
        "canonical_identifier": f"{kind}:{identifier.strip().lower()}",
        "provider_identifiers": provider_identifiers,
        "name": name,
        "aliases": _text_list(raw.get("aliases")),
        "mold_variants": _value_list(raw.get("mold_variants") or raw.get("variants")),
        "image_urls": _text_list(
            raw.get("image_urls") or raw.get("images") or raw.get("image_url")
        ),
        "first_known_year": first_year,
        "last_known_year": last_year,
        **common,
    }


def _known_year_range(raw: Mapping[str, Any]) -> tuple[int | None, int | None]:
    years = (
        raw.get("known_year_range")
        if isinstance(raw.get("known_year_range"), Mapping)
        else {}
    )
    first = raw.get("first_known_year", years.get("first"))
    last = raw.get("last_known_year", years.get("last"))
    try:
        first_year = int(first) if first is not None else None
        last_year = int(last) if last is not None else None
    except (TypeError, ValueError) as exc:
        raise ServiceIncompleteDataError(
            "Provider record contains an invalid year"
        ) from exc
    if first_year is not None and not 1949 <= first_year <= 2100:
        raise ServiceIncompleteDataError(
            "Provider record contains an invalid first year"
        )
    if last_year is not None and not 1949 <= last_year <= 2100:
        raise ServiceIncompleteDataError(
            "Provider record contains an invalid last year"
        )
    if first_year is not None and last_year is not None and last_year < first_year:
        raise ServiceIncompleteDataError("Provider record has an inverted year range")
    return first_year, last_year


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ServiceIncompleteDataError(
                "Provider source timestamp is invalid"
            ) from exc
    return None


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _text_list(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value] if value else []
    return list(
        dict.fromkeys(str(item).strip() for item in values if str(item).strip())
    )


def _value_list(value: Any) -> list[Any]:
    values = value if isinstance(value, list) else [value] if value else []
    result: list[Any] = []
    for item in values:
        if item not in result:
            result.append(item)
    return result
