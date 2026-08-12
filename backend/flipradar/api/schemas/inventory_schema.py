from uuid import UUID

from pydantic import BaseModel, Field


class InventoryElementResponse(BaseModel):
    id: UUID
    element_number: str
    part_number: str
    part_name: str
    color: str
    image_url: str | None = None


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


class MissingPartsChecklistResponse(BaseModel):
    set_number: str
    set_name: str
    required_parts: int
    owned_parts: int
    missing_parts: int
    lines: list[ChecklistLineResponse]
