from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

JsonDocument = JSON().with_variant(JSONB(), "postgresql")
