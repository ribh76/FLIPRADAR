from uuid import UUID

from pydantic import BaseModel, Field


class InventoryElementResponse(BaseModel):
    id: UUID
    element_number: str
    part_number: str
    part_name: str
    color: str
    image_url: str | None = None
    estimated_unit_cost: float | None = None


class InventoryItemResponse(BaseModel):
    id: UUID
    quantity: int
    element: InventoryElementResponse


class InventoryQuantityUpdate(BaseModel):
    quantity: int = Field(ge=0, le=100_000)


class ChecklistAdjustmentUpdate(BaseModel):
    manual_adjustment: int = Field(default=0, ge=-100_000, le=100_000)
    substitute_element_id: UUID | None = None


class ChecklistLineResponse(BaseModel):
    requirement_id: UUID
    element: InventoryElementResponse
    required_quantity: int
    adjusted_quantity: int
    owned_quantity: int
    missing_quantity: int
    substitute_element: InventoryElementResponse | None = None
    substitution_candidates: list[InventoryElementResponse] = Field(
        default_factory=list
    )
    purchase_item_id: UUID | None = None
    purchased: bool = False
    actual_unit_cost: float | None = None


class MissingPartsChecklistResponse(BaseModel):
    set_number: str
    set_name: str
    required_parts: int
    owned_parts: int
    missing_parts: int
    completeness_percent: float
    estimated_replacement_cost: float
    completed_set_value: float | None = None
    completeness_adjusted_value: float | None = None
    purchase_price: float | None = None
    projected_net_value: float | None = None
    lines: list[ChecklistLineResponse]


class PurchaseItemUpdate(BaseModel):
    purchased: bool
    actual_unit_cost: float | None = Field(default=None, ge=0)
