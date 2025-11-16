from pydantic import BaseModel
from typing import Optional


class F1Stint(BaseModel):
    meeting_key: int
    session_key: int
    stint_number: int
    driver_number: int
    lap_start: int
    lap_end: int
    compound: Optional[str] = None
    tyre_age_at_start: Optional[int] = None


class GetF1StintsResponse(BaseModel):
    stints: list[F1Stint]


