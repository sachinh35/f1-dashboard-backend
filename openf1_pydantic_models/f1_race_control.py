"""
Pydantic models for OpenF1 Race Control API responses.
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class F1RaceControlEvent(BaseModel):
    """Model for race control event from OpenF1 API."""
    date: datetime
    session_key: int
    meeting_key: int
    category: Optional[str] = None  # e.g., "Flag", "Safety", "Other"
    message: str
    scope: Optional[str] = None  # "Track", "Sector", "Driver", etc.
    sector: Optional[int] = None  # Sector number if sector-specific
    driver_number: Optional[int] = None  # Driver number if driver-specific
    flag: Optional[str] = None  # Flag type: "YELLOW", "RED", "GREEN", etc.
    
    class Config:
        # Allow extra fields from API that we don't use
        extra = "ignore"

