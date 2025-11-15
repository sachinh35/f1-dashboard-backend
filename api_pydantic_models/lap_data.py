"""
Pydantic models for lap data API requests and responses.
These models represent the structure of data sent to/from our API endpoints.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Union
from datetime import datetime


class LapDataRequest(BaseModel):
    """Request model for lap data API endpoint."""
    driver_numbers: List[int] = Field(..., description="List of driver numbers to fetch lap data for", min_items=1)


class LapDataResponse(BaseModel):
    """Response model for a single lap data entry."""
    meeting_key: int
    session_key: int
    driver_number: int
    lap_number: int
    date_start: Optional[datetime] = None
    duration_sector_1: Optional[float] = None
    duration_sector_2: Optional[float] = None
    duration_sector_3: Optional[float] = None
    lap_duration: Optional[float] = None
    i1_speed: Optional[int] = None
    i2_speed: Optional[int] = None
    st_speed: Optional[int] = None
    is_pit_out_lap: bool
    segments_sector_1: Optional[List[Optional[int]]] = None
    segments_sector_2: Optional[List[Optional[int]]] = None
    segments_sector_3: Optional[List[Optional[int]]] = None


class GetSessionLapDataResponse(BaseModel):
    """Response model for session lap data API endpoint."""
    session_key: int
    lap_data: List[LapDataResponse]


class LapDataDB(BaseModel):
    """
    Model representing lap data as stored in PostgreSQL database.
    Includes database-specific fields like id, created_at, updated_at.
    """
    id: Optional[int] = None
    meeting_key: int
    session_key: int
    driver_number: int
    lap_number: int
    date_start: Optional[datetime] = None
    duration_sector_1: Optional[float] = None
    duration_sector_2: Optional[float] = None
    duration_sector_3: Optional[float] = None
    lap_duration: Optional[float] = None
    i1_speed: Optional[int] = None
    i2_speed: Optional[int] = None
    st_speed: Optional[int] = None
    is_pit_out_lap: bool = False
    segments_sector_1: Optional[List[Optional[int]]] = None
    segments_sector_2: Optional[List[Optional[int]]] = None
    segments_sector_3: Optional[List[Optional[int]]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

