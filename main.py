from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from utils import race_session
from api_pydantic_models.races import GetAvailableYearsResponse, GetRacesForYearsResponse
from api_pydantic_models.race_sesssions import GetAllSessionTypesResponse, SessionType, GetSessionResultsResponse
import logging

app = FastAPI()

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
