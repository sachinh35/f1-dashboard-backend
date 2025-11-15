from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from utils import race_session, lap_data
from api_pydantic_models.races import GetAvailableYearsResponse, GetRacesForYearsResponse
from api_pydantic_models.race_sesssions import GetAllSessionTypesResponse, SessionType, GetSessionResultsResponse
from api_pydantic_models.lap_data import LapDataRequest, GetSessionLapDataResponse
from utils.database import DatabaseManager
import logging

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
        print("session_key: {}".format(session_key))
        results = await race_session.get_results_by_session_key(session_key=session_key)
        print("results: {}".format(results))
        return GetSessionResultsResponse(results=results)
    except Exception as e:
        print(e)
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
        
        print(f"Fetching lap data for session_key: {session_key}, drivers: {request.driver_numbers}")
        lap_data_list = await lap_data.get_lap_data_for_session(
            session_key=session_key,
            driver_numbers=request.driver_numbers
        )
        
        print(f"Returning {len(lap_data_list)} lap records")
        return GetSessionLapDataResponse(
            session_key=session_key,
            lap_data=lap_data_list
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_session_lap_data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch lap data: {str(e)}")
