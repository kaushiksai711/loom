from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class ConceptBase(BaseModel):
    label: str
    summary: str
    status: str = "seed"  # seed, crystallized, dormant
    tags: List[str] = []
    metadata: Dict[str, Any] = {}

class ConceptCreate(ConceptBase):
    pass

class Concept(ConceptBase):
    key: str = Field(alias="_key")
    id: str = Field(alias="_id")
    created_at: datetime
    last_verified: Optional[datetime] = None
    verification_count: int = 0
    embedding: Optional[List[float]] = None

    class Config:
        populate_by_name = True
