from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class RelationshipBase(BaseModel):
    type: str
    weight: float = 1.0
    inferred_by: Optional[str] = None

class RelationshipCreate(RelationshipBase):
    from_node: str = Field(alias="_from")
    to_node: str = Field(alias="_to")

class Relationship(RelationshipBase):
    key: str = Field(alias="_key")
    id: str = Field(alias="_id")
    from_node: str = Field(alias="_from")
    to_node: str = Field(alias="_to")
    created_at: datetime

    class Config:
        populate_by_name = True
