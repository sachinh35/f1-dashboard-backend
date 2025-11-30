from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from utils import race_session, lap_data, stints, race_control, live_stream, f1_auth, live_db
from utils.websocket_manager import manager
from api_pydantic_models.races import GetAvailableYearsResponse, GetRacesForYearsResponse
from api_pydantic_models.race_sesssions import GetAllSessionTypesResponse, SessionType, GetSessionResultsResponse
from api_pydantic_models.lap_data import LapDataRequest, GetSessionLapDataResponse
from api_pydantic_models.stints import GetSessionStintsResponse
from api_pydantic_models.race_control import GetSessionRaceControlEventsResponse
from api_pydantic_models.live_stream import (
    StartStreamRequest, 
    StartStreamResponse,
    AuthenticateRequest,
    AuthenticateResponse
)
from utils.database import DatabaseManager
import logging
import os

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


@app.post("/authenticate-f1tv", response_model=AuthenticateResponse)
async def authenticate_f1tv(request: AuthenticateRequest) -> AuthenticateResponse:
    """
    Authenticate with F1 TV Pro using email and password.
    
    Args:
        request: Request containing email and password
        
    Returns:
        AuthenticateResponse with access token and cookies
    """
    try:
        logging.info("Request: F1 TV Pro authentication for email: %s", request.email)
        
        auth_result = await f1_auth.authenticate_f1tv(
            email=request.email,
            password=request.password
        )
        
        logging.info("Response: F1 TV Pro authentication successful")
        
        return AuthenticateResponse(
            success=True,
            access_token=auth_result["access_token"],
            cookies=auth_result.get("cookies"),
            message="Authentication successful"
        )
        
    except Exception as e:
        logging.exception("Error in F1 TV Pro authentication")
        raise HTTPException(
            status_code=401,
            detail=f"F1 TV Pro authentication failed: {str(e)}"
        )


@app.post("/start-live-stream", response_model=StartStreamResponse)
async def start_live_stream(request: StartStreamRequest) -> StartStreamResponse:
    """
    Start a live stream from F1's SignalR client.
    
    - Receives F1 TV Pro authentication tokens from frontend
    - Connects to F1 SignalR hub
    - Logs all events to console and saves to a unique file
    - Returns stream information
    
    Args:
        request: Request containing access_token and optional refresh_token
        
    Returns:
        StartStreamResponse with stream ID and log file path
    """
    try:
        logging.info("Request: starting live stream")
        
        token = request.access_token
        
        # If no token provided, try to load saved token
        if not token:
            logging.info("No access token in request, attempting to load saved token")
            saved_token = f1_auth.get_saved_token()
            if saved_token and f1_auth.validate_subscription_token(saved_token):
                token = saved_token
                logging.info("Using saved subscription token")
            else:
                raise HTTPException(
                    status_code=400,
                    detail="No access token provided and no valid saved token found. Please authenticate first."
                )
        
        # Start the stream
        streamer = live_stream.start_stream(
            access_token=token,
            refresh_token=request.refresh_token,
            cookies=request.cookies
        )
        
        stream_info = streamer.get_stream_info()
        
        logging.info(
            "Response: live stream started successfully. stream_id=%s, log_file=%s",
            stream_info["stream_id"],
            stream_info["log_file"]
        )
        
        return StartStreamResponse(
            success=True,
            message="Live stream started successfully",
            stream_id=stream_info["stream_id"],
            log_file=stream_info["log_file"] or "unknown"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error starting live stream")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start live stream: {str(e)}"
        )


@app.websocket("/ws/live-timing/{stream_id}")
async def websocket_endpoint(websocket: WebSocket, stream_id: str):
    await manager.connect(websocket, stream_id)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except Exception:
        manager.disconnect(websocket, stream_id)
@app.post("/simulate-live-stream")
async def simulate_live_stream():
    """Start a simulated live stream from a log file."""
    try:
        # Find the most recent log file or use a specific one
        # For this task, we use the specific file requested by the user
        log_file = "stream_logs/f1_stream_1764517880_race_qatar.jsonl"
        
        if not os.path.exists(log_file):
            raise HTTPException(status_code=404, detail=f"Log file not found: {log_file}")
            
        streamer = live_stream.start_simulation(log_file)
        
        return {
            "message": "Simulation started",
            "stream_id": streamer.stream_id,
            "log_file": str(streamer.log_file_path)
        }
    except Exception as e:
        logging.error(f"Error starting simulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/live-timing/{stream_id}")
async def get_live_timing_data(stream_id: str):
    """Fetch historical lap times for a live stream."""
    try:
        lap_times = await live_db.get_live_lap_times(stream_id)
        return {"lap_times": lap_times}
    except Exception as e:
        logging.exception("Error fetching live timing data")
        raise HTTPException(status_code=500, detail=str(e))
