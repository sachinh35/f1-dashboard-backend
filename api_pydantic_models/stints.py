from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class StintDB(BaseModel):
    id: Optional[int] = None
    meeting_key: int
    session_key: int
    driver_number: int
    stint_number: int
    lap_start: int
    lap_end: int
    compound: Optional[str] = None
    tyre_age_at_start: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StintResponse(BaseModel):
    meeting_key: int
    session_key: int
    driver_number: int
    stint_number: int
    lap_start: int
    lap_end: int
    compound: Optional[str] = None
    tyre_age_at_start: Optional[int] = None


class GetSessionStintsResponse(BaseModel):
    session_key: int
    stints: List[StintResponse]


