"""
Pydantic models for race control API requests and responses.
"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class RaceControlEventDB(BaseModel):
    """Database model for race control event."""
    id: Optional[int] = None
    meeting_key: int
    session_key: int
    date: datetime
    category: str
    message: str
    scope: Optional[str] = None
    sector: Optional[int] = None
    driver_number: Optional[int] = None
    flag: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RaceControlEventResponse(BaseModel):
    """API response model for race control event."""
    session_key: int
    date: str
    category: str
    message: str
    scope: Optional[str] = None
    sector: Optional[int] = None
    driver_number: Optional[int] = None
    flag: Optional[str] = None


class GetSessionRaceControlEventsResponse(BaseModel):
    """Response model for getting race control events for a session."""
    session_key: int
    events: List[RaceControlEventResponse]

