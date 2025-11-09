from pydantic import BaseModel
from datetime import datetime
from typing import List, Union


class F1Session(BaseModel):
    circuit_key: int
    circuit_short_name: str
    country_code: str
    country_key: int
    country_name: str
    date_end: datetime
    date_start: datetime
    gmt_offset: str
    location: str
    meeting_key: int
    session_key: int
    session_name: str
    session_type: str
    year: int


class F1SessionResult(BaseModel):
    dnf: bool
    dns: bool
    dsq: bool
    driver_number: int
    number_of_laps: int
    meeting_key: Union[int, str]
    session_key: int

    # --- Fix 2: Type Correction for duration, gap_to_leader, and position ---

    # 'duration' and 'gap_to_leader' are simple float or None, NOT List[Union[float, None]]
    duration: Union[float, None] = None
    gap_to_leader: Union[float, str, int, None] = None 
    # 'gap_to_leader' can be a float, an int (0 for the leader), a string ('+1 LAP'), or None.

    # 'position' is an int or None, NOT just an int
    position: Union[int, None] = None


class GetF1SessionsResponse(BaseModel):
    sessions: List[F1Session]


class GetF1SessionResultResponse(BaseModel):
    session_result: List[F1SessionResult]
