"""
Pydantic models for OpenF1 API lap data responses.
These models represent the raw data structure from the OpenF1 API.
"""
from pydantic import BaseModel
from typing import List, Optional, Union
from datetime import datetime


class F1LapData(BaseModel):
    """
    Model representing a single lap from OpenF1 API.
    Matches the structure returned by https://api.openf1.org/v1/laps
    """
    meeting_key: int
    session_key: int
    driver_number: int
    lap_number: int
    date_start: Optional[datetime] = None
    duration_sector_1: Optional[float] = None
    duration_sector_2: Optional[float] = None
    duration_sector_3: Optional[float] = None
    i1_speed: Optional[int] = None
    i2_speed: Optional[int] = None
    is_pit_out_lap: bool = False
    lap_duration: Optional[float] = None
    segments_sector_1: Optional[List[Optional[int]]] = None
    segments_sector_2: Optional[List[Optional[int]]] = None
    segments_sector_3: Optional[List[Optional[int]]] = None
    st_speed: Optional[int] = None


class GetF1LapsResponse(BaseModel):
    """Response wrapper for OpenF1 laps API."""
    laps: List[F1LapData]

