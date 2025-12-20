from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class SessionBase(BaseModel):
    title: str
    goal: str
    topics: List[str] = []
    status: str = "active" # active, finalized

class SessionCreate(SessionBase):
    pass

class Session(SessionBase):
    key: str = Field(alias="_key")
    id: str = Field(alias="_id")
    created_at: datetime
    finalized_at: Optional[datetime] = None
    harvested_nodes: List[str] = []
    metrics: Dict[str, Any] = {}

    class Config:
        populate_by_name = True
