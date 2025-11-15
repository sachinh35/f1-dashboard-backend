"""
Utility functions for fetching and managing lap data.
Handles the logic for checking DB cache, fetching from OpenF1 API, and storing data.
"""
import httpx
from typing import List, Optional
from datetime import datetime, timezone
from constants.openf1_api_endpoints import LAPS_API_URL
from openf1_pydantic_models.f1_laps import F1LapData, GetF1LapsResponse
from api_pydantic_models.lap_data import LapDataDB, LapDataResponse
from utils.database import (
    check_session_data_exists,
    get_lap_data_from_db,
    insert_lap_data_batch
)


async def fetch_laps_from_openf1(session_key: int) -> List[F1LapData]:
    """
    Fetch lap data from OpenF1 API for a given session.
    
    Args:
        session_key: Session identifier
        
    Returns:
        List of F1LapData objects from OpenF1 API
    """
    parameters = {
        "session_key": session_key
    }
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(LAPS_API_URL, params=parameters)
            response.raise_for_status()
            
            # Parse response into Pydantic models
            laps_data = [F1LapData(**lap) for lap in response.json()]
            return laps_data
    except Exception as e:
        print(f"Error fetching lap data from OpenF1 API: {e}")
        raise e


def normalize_datetime(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Normalize datetime to naive (timezone-unaware) for PostgreSQL TIMESTAMP storage.
    If datetime is timezone-aware, convert to UTC and remove timezone info.
    If datetime is naive, return as-is.
    
    Args:
        dt: Datetime object (may be timezone-aware or naive)
        
    Returns:
        Naive datetime object suitable for PostgreSQL TIMESTAMP
    """
    if dt is None:
        return None
    
    if dt.tzinfo is not None:
        # Convert to UTC first, then remove timezone info to make it naive
        utc_dt = dt.astimezone(timezone.utc)
        return utc_dt.replace(tzinfo=None)
    else:
        # Already naive, return as-is
        return dt


def convert_openf1_to_db_model(openf1_lap: F1LapData) -> LapDataDB:
    """
    Convert OpenF1 API lap data model to database model.
    Handles timezone conversion for datetime fields.
    
    Args:
        openf1_lap: F1LapData from OpenF1 API
        
    Returns:
        LapDataDB model for database storage
    """
    return LapDataDB(
        meeting_key=openf1_lap.meeting_key,
        session_key=openf1_lap.session_key,
        driver_number=openf1_lap.driver_number,
        lap_number=openf1_lap.lap_number,
        date_start=normalize_datetime(openf1_lap.date_start),
        duration_sector_1=openf1_lap.duration_sector_1,
        duration_sector_2=openf1_lap.duration_sector_2,
        duration_sector_3=openf1_lap.duration_sector_3,
        lap_duration=openf1_lap.lap_duration,
        i1_speed=openf1_lap.i1_speed,
        i2_speed=openf1_lap.i2_speed,
        st_speed=openf1_lap.st_speed,
        is_pit_out_lap=openf1_lap.is_pit_out_lap,
        segments_sector_1=openf1_lap.segments_sector_1,
        segments_sector_2=openf1_lap.segments_sector_2,
        segments_sector_3=openf1_lap.segments_sector_3
    )


def convert_db_to_response_model(db_lap: LapDataDB) -> LapDataResponse:
    """
    Convert database model to API response model.
    
    Args:
        db_lap: LapDataDB from database
        
    Returns:
        LapDataResponse for API response
    """
    return LapDataResponse(
        meeting_key=db_lap.meeting_key,
        session_key=db_lap.session_key,
        driver_number=db_lap.driver_number,
        lap_number=db_lap.lap_number,
        date_start=db_lap.date_start,
        duration_sector_1=db_lap.duration_sector_1,
        duration_sector_2=db_lap.duration_sector_2,
        duration_sector_3=db_lap.duration_sector_3,
        lap_duration=db_lap.lap_duration,
        i1_speed=db_lap.i1_speed,
        i2_speed=db_lap.i2_speed,
        st_speed=db_lap.st_speed,
        is_pit_out_lap=db_lap.is_pit_out_lap,
        segments_sector_1=db_lap.segments_sector_1,
        segments_sector_2=db_lap.segments_sector_2,
        segments_sector_3=db_lap.segments_sector_3
    )


async def get_lap_data_for_session(
    session_key: int,
    driver_numbers: List[int]
) -> List[LapDataResponse]:
    """
    Main function to get lap data for a session and drivers.
    Implements cache-first strategy: check DB first, then fetch from API if needed.
    
    Args:
        session_key: Session identifier
        driver_numbers: List of driver numbers to fetch
        
    Returns:
        List of LapDataResponse objects filtered by driver_numbers
    """
    # Check if data exists in database
    data_exists = await check_session_data_exists(session_key, driver_numbers)
    
    if data_exists:
        # Fetch from database
        print(f"Lap data found in DB for session {session_key}, drivers {driver_numbers}")
        db_laps = await get_lap_data_from_db(session_key, driver_numbers)
    else:
        # Fetch from OpenF1 API
        print(f"Lap data not in DB for session {session_key}, fetching from OpenF1 API")
        openf1_laps = await fetch_laps_from_openf1(session_key)
        
        # Convert to DB models
        db_lap_models = [convert_openf1_to_db_model(lap) for lap in openf1_laps]
        
        # Store in database (batch insert)
        if db_lap_models:
            print(f"Inserting {len(db_lap_models)} lap records into database")
            await insert_lap_data_batch(db_lap_models)
        
        # Fetch from database to ensure consistency (includes any updates from ON CONFLICT)
        db_laps = await get_lap_data_from_db(session_key, driver_numbers)
    
    # Filter by requested driver numbers and convert to response model
    filtered_laps = [
        convert_db_to_response_model(lap) 
        for lap in db_laps 
        if lap.driver_number in driver_numbers
    ]
    
    return filtered_laps

