from pydantic import BaseModel
from typing import Optional

class DriverInfo(BaseModel):
    # https://openf1.org/#drivers
    meeting_key: int
    session_key: int
    driver_number: int
    broadcast_name: str
    full_name: str
    name_acronym: str
    team_name: str
    team_colour: str
    first_name: str
    last_name: str
    headshot_url: Optional[str]
    country_code: str