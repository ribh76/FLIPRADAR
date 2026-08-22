"""Normalize provider part records into a stable catalog representation."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast

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
    if not isinstance(raw_record, Mapping):
        raise ServiceIncompleteDataError("Provider record must be an object")
    provider = provider.strip().lower()
    if not provider:
        raise ServiceIncompleteDataError("Catalog provider is required")
    fetched_at = fetched_at or datetime.now(UTC)
    raw_source = raw_record.get("source")
    if raw_source is not None and not isinstance(raw_source, Mapping):
        raise ServiceIncompleteDataError("Provider source metadata must be an object")
    source = raw_source or {}
    common = {
        "source_name": _optional_text(source.get("name"))
        or f"{provider.title()} catalog",
        "source_url": _optional_text(source.get("url")),
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
    identifier = _identifier_for(raw, kind)
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
    payload = {
        "canonical_identifier": f"{kind}:{identifier.strip().lower()}",
        "provider_identifiers": provider_identifiers,
        "name": name,
        "aliases": _text_list(raw.get("aliases")),
        "mold_variants": _value_list(raw.get("mold_variants") or raw.get("variants")),
        "image_urls": _text_list(
            raw.get("image_urls") or raw.get("images") or raw.get("image_url")
        ),
        "quality_flags": _quality_flags(
            raw,
            aliases=raw.get("aliases"),
            images=raw.get("image_urls") or raw.get("images") or raw.get("image_url"),
            first_year=first_year,
            last_year=last_year,
            source_updated_at=common["source_updated_at"],
        ),
        "first_known_year": first_year,
        "last_known_year": last_year,
        **common,
    }
    if kind == "part":
        market_price = _market_price(raw.get("market_price"))
        payload["market_price"] = market_price
        payload["market_price_currency"] = (
            _optional_text(raw.get("market_price_currency")) or "USD"
            if market_price is not None
            else None
        )
    return payload


def _market_price(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ServiceIncompleteDataError("Provider market price is invalid") from exc
    if price < 0:
        raise ServiceIncompleteDataError("Provider market price cannot be negative")
    return price.quantize(Decimal("0.01"))


def _identifier_for(raw: Mapping[str, Any], kind: str) -> str | None:
    identifiers = {
        "category": ("canonical_identifier", "category_id", "id"),
        "color": ("canonical_identifier", "color_id", "id"),
        "part": ("canonical_identifier", "part_num", "part_number", "id"),
        "element": ("canonical_identifier", "element_id", "id"),
    }
    identifier = _first_text(*(raw.get(key) for key in identifiers[kind]))
    if identifier and identifier.lower().startswith(f"{kind}:"):
        return identifier.split(":", 1)[1].strip() or None
    return identifier


def _known_year_range(raw: Mapping[str, Any]) -> tuple[int | None, int | None]:
    years_raw = raw.get("known_year_range")
    years = cast(Mapping[str, Any], years_raw) if isinstance(years_raw, Mapping) else {}
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
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ServiceIncompleteDataError(
                "Provider source timestamp is invalid"
            ) from exc
    else:
        raise ServiceIncompleteDataError("Provider source timestamp is invalid")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        raise ServiceIncompleteDataError(
            "Provider text collection must be a string or list"
        )
    normalized: list[str] = []
    for item in values:
        if isinstance(item, (Mapping, list, tuple, set)):
            raise ServiceIncompleteDataError(
                "Provider text collection contains invalid data"
            )
        text = str(item).strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _value_list(value: Any) -> list[Any]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    result: list[Any] = []
    for item in values:
        if item not in result:
            result.append(item)
    return result


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (Mapping, list, tuple, set)):
        raise ServiceIncompleteDataError("Provider source text is invalid")
    return _first_text(value)


def _quality_flags(
    raw: Mapping[str, Any],
    *,
    aliases: Any,
    images: Any,
    first_year: int | None,
    last_year: int | None,
    source_updated_at: datetime | None,
) -> list[str]:
    flags = _text_list(raw.get("quality_flags"))
    if not _text_list(aliases):
        flags.append("missing_aliases")
    if not _text_list(images):
        flags.append("missing_images")
    if first_year is None and last_year is None:
        flags.append("missing_known_year_range")
    if source_updated_at is None:
        flags.append("source_timestamp_missing")
    return list(dict.fromkeys(flags))
