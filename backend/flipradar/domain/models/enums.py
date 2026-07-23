from enum import StrEnum


class MarketplaceName(StrEnum):
    EBAY = "ebay"
    BRICKLINK = "bricklink"


class ListingCondition(StrEnum):
    NEW = "new"
    USED = "used"
    UNKNOWN = "unknown"


class PortfolioCondition(StrEnum):
    NEW = "new"
    USED = "used"
    SEALED = "sealed"
    UNKNOWN = "unknown"


class SnapshotCondition(StrEnum):
    NEW = "new"
    USED = "used"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ListingStatus(StrEnum):
    ACTIVE = "active"
    SOLD = "sold"
    ENDED = "ended"
    REMOVED = "removed"


class RecommendationType(StrEnum):
    BUY_SET = "buy_set"
    SELL_SET = "sell_set"
    HOLD_VS_SELL = "hold_vs_sell"
    BUY_VS_PASS = "buy_vs_pass"


class RecommendationDecision(StrEnum):
    BUY = "BUY"
    PASS = "PASS"
    SELL = "SELL"
    HOLD = "HOLD"
    WATCH = "WATCH"


def sql_values(enum_type: type[StrEnum]) -> str:
    return ", ".join(f"'{item.value}'" for item in enum_type)
