"""
Session Signal Model
Tracks user interactions with scaffolds for learning analytics.
"""
from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime

class SessionSignal(BaseModel):
    """
    Represents a single user interaction with a concept scaffold.
    Used for Layer B4: Signal Capture.
    """
    session_id: str
    concept_id: str
    format_chosen: Literal["hands_on", "visual", "socratic", "textual"]
    timestamp: Optional[datetime] = None
    dwell_time_ms: int = 0
    time_since_last_interaction_ms: int = 0
    interaction_type: Literal["scaffold_click", "tab_switch", "content_scroll"] = "scaffold_click"

class SessionSignalCreate(BaseModel):
    """Request body for creating a signal (subset of fields)."""
    concept_id: str
    format_chosen: Literal["hands_on", "visual", "socratic", "textual"]
    dwell_time_ms: int = 0
    time_since_last_interaction_ms: int = 0
    interaction_type: Literal["scaffold_click", "tab_switch", "content_scroll"] = "scaffold_click"
