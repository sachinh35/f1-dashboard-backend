from openf1_pydantic_models.f1_sessions import GetF1SessionsResponse, F1SessionResult, GetF1SessionResultResponse
from constants.openf1_api_endpoints import SESSIONS_API_URL, SESSION_RESULTS_API_URL, DRIVERS_API_URL
from api_pydantic_models.races import RaceInfo
from api_pydantic_models.race_sesssions import EnrichedF1SessionResult
from openf1_pydantic_models.f1_drivers import DriverInfo
import httpx
from typing import List


async def get_races_by_year(year: int) -> list[RaceInfo]:
    parameters = {
        "year": year,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(SESSIONS_API_URL, params=parameters)

            all_races = GetF1SessionsResponse(sessions=response.json())
            race_info = [RaceInfo(session_key=s.session_key, location=s.location, session_name=s.session_name) for s in
                         all_races.sessions]
            return sorted(race_info, key=lambda x: x.location)
    except Exception as e:
        print(e)
        raise e


async def get_results_by_session_key(session_key: int) -> List[EnrichedF1SessionResult]:
    parameters = {
        "session_key": session_key
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            print("Invoking GetSessionResponse")
            response = await client.get(SESSION_RESULTS_API_URL, params=parameters)
            validated_response = GetF1SessionResultResponse(session_result=response.json())

            # Sort by DNF status (DNFs at the back) and then by position
            sorted_results = sorted(validated_response.session_result, key=lambda x: (x.dnf, x.position is None, x.position))

            # Collect all driver numbers into a list
            driver_numbers = [result.driver_number for result in sorted_results]

            if not driver_numbers:
                return []

            # Fetch all driver info in a single API call
            driver_params = {
                "driver_number": driver_numbers,
                "session_key": session_key
            }
            driver_response = await client.get(DRIVERS_API_URL, params=driver_params)
            print("driver_response: {}".format(driver_response.json()))
            driver_info_list = [DriverInfo(**driver) for driver in driver_response.json()]

            # Create a lookup map for efficient access
            driver_info_map = {driver.driver_number: driver for driver in driver_info_list}

            enriched_results: List[EnrichedF1SessionResult] = []
            for result in sorted_results:
                driver_info = driver_info_map.get(result.driver_number)
                if driver_info:
                    enriched_result = EnrichedF1SessionResult(
                        dnf=result.dnf,
                        dns=result.dns,
                        dsq=result.dsq,
                        driver_number=result.driver_number,
                        number_of_laps=result.number_of_laps,
                        meeting_key=result.meeting_key,
                        session_key=result.session_key,
                        duration=result.duration,
                        gap_to_leader=result.gap_to_leader,
                        position=result.position,
                        full_name=driver_info.full_name,
                        name_acronym=driver_info.name_acronym,
                        first_name=driver_info.first_name,
                        last_name=driver_info.last_name,
                        country_code=driver_info.country_code,
                    )
                    enriched_results.append(enriched_result)

            return enriched_results
    except Exception as e:
        print(e)
        raise e
