from pydantic import BaseModel
from typing import List, Union
from enum import Enum


class SessionType(str, Enum):
    QUALIFYING = "Qualifying"
    RACE = "Race"


class GetAllSessionTypesResponse(BaseModel):
    session_types: List[SessionType]


class EnrichedF1SessionResult(BaseModel):
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
    full_name: str
    name_acronym: str
    first_name: str
    last_name: str
    country_code: str


class GetSessionResultsResponse(BaseModel):
    results: List[EnrichedF1SessionResult]
