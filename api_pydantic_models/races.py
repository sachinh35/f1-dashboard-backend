from pydantic import BaseModel
from typing import List


class GetAvailableYearsResponse(BaseModel):
    years_list: List[int]


class RaceInfo(BaseModel):
    session_key: int
    location: str
    session_name: str
    country_code: str


class GetRacesForYearsResponse(BaseModel):
    all_races: List[RaceInfo]
