from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from utils import race_session, lap_data, stints, race_control
from api_pydantic_models.races import GetAvailableYearsResponse, GetRacesForYearsResponse
from api_pydantic_models.race_sesssions import GetAllSessionTypesResponse, SessionType, GetSessionResultsResponse
from api_pydantic_models.lap_data import LapDataRequest, GetSessionLapDataResponse
from api_pydantic_models.stints import GetSessionStintsResponse
from api_pydantic_models.race_control import GetSessionRaceControlEventsResponse
from utils.database import DatabaseManager
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)

app = FastAPI()


@app.on_event("startup")
async def startup_event():
    """Initialize database connection pool on startup."""
    await DatabaseManager.get_pool()


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection pool on shutdown."""
    await DatabaseManager.close_pool()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change in production!
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/years")
def get_years() -> GetAvailableYearsResponse:
    return GetAvailableYearsResponse(years_list=list(range(2023, 2026)))


@app.get("/races/{year}")
async def get_races_for_year(year: int) -> GetRacesForYearsResponse:
    try:
        races = await race_session.get_races_by_year(year)
        return GetRacesForYearsResponse(all_races=races)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch races")


@app.get("/session-types")
def get_session_types() -> GetAllSessionTypesResponse:
    return GetAllSessionTypesResponse(session_types=[SessionType.QUALIFYING, SessionType.RACE])


@app.get("/session-results/{session_key}")
async def get_session_results(session_key: int) -> GetSessionResultsResponse:
    try:
        logging.info("Request: session results for session_key=%s", session_key)
        results = await race_session.get_results_by_session_key(session_key=session_key)
        logging.info("Response: returning %d session results for session_key=%s", len(results), session_key)
        return GetSessionResultsResponse(results=results)
    except Exception as e:
        logging.exception("Error in get_session_results for session_key=%s", session_key)
        raise e


@app.post("/session-lap-data/{session_key}")
async def get_session_lap_data(
    session_key: int,
    request: LapDataRequest
) -> GetSessionLapDataResponse:
    """
    Get lap data for a specific session and driver(s).
    
    - Checks PostgreSQL database first
    - If data not found, fetches from OpenF1 API, stores in DB, then returns
    - Returns data filtered by requested driver_numbers
    
    Args:
        session_key: Session identifier (path parameter)
        request: Request body containing driver_numbers list
        
    Returns:
        GetSessionLapDataResponse with lap data for requested drivers
    """
    try:
        if not request.driver_numbers:
            raise HTTPException(
                status_code=400, 
                detail="driver_numbers list cannot be empty"
            )
        
        logging.info("Request: lap data for session_key=%s drivers=%s", session_key, request.driver_numbers)
        lap_data_list = await lap_data.get_lap_data_for_session(
            session_key=session_key,
            driver_numbers=request.driver_numbers
        )
        logging.info("Response: returning %d lap records for session_key=%s", len(lap_data_list), session_key)
        return GetSessionLapDataResponse(
            session_key=session_key,
            lap_data=lap_data_list
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in get_session_lap_data for session_key=%s", session_key)
        raise HTTPException(status_code=500, detail=f"Failed to fetch lap data: {str(e)}")


@app.get("/session-stints/{session_key}")
async def get_session_stints(session_key: int) -> GetSessionStintsResponse:
    """
    Get stints for a specific session.
    - Checks DB first
    - If absent, fetches from OpenF1, stores, then returns
    """
    try:
        logging.info("Request: stints for session_key=%s", session_key)
        stint_list = await stints.get_stints_for_session(session_key)
        logging.info("Response: returning %d stints for session_key=%s", len(stint_list), session_key)
        return GetSessionStintsResponse(session_key=session_key, stints=stint_list)
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in get_session_stints for session_key=%s", session_key)
        raise HTTPException(status_code=500, detail=f"Failed to fetch stints: {str(e)}")


@app.get("/session-race-control-events/{session_key}")
async def get_session_race_control_events(session_key: int) -> GetSessionRaceControlEventsResponse:
    """
    Get race control events for a specific session.
    - Checks DB first
    - If absent, fetches from OpenF1, stores, then returns
    """
    try:
        logging.info("Request: race control events for session_key=%s", session_key)
        event_list = await race_control.get_race_control_events_for_session(session_key)
        logging.info("Response: returning %d race control events for session_key=%s", len(event_list), session_key)
        return GetSessionRaceControlEventsResponse(session_key=session_key, events=event_list)
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in get_session_race_control_events for session_key=%s", session_key)
        raise HTTPException(status_code=500, detail=f"Failed to fetch race control events: {str(e)}")
