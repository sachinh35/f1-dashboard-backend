"""
Utility functions for fetching and managing race control events.
Handles the logic for checking DB cache, fetching from OpenF1 API, and storing data.
"""
import httpx
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import HTTPException
from constants.openf1_api_endpoints import RACE_CONTROL_API_URL
from openf1_pydantic_models.f1_race_control import F1RaceControlEvent
from api_pydantic_models.race_control import RaceControlEventDB, RaceControlEventResponse
from utils.database import (
    check_race_control_events_exists,
    get_race_control_events_from_db,
    insert_race_control_events_batch,
)
import logging

logger = logging.getLogger(__name__)


def normalize_datetime(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Normalize datetime to naive (timezone-unaware) for PostgreSQL TIMESTAMP storage.
    If datetime is timezone-aware, convert to UTC and remove timezone info.
    If datetime is naive, return as-is.
    """
    if dt is None:
        return None
    
    if dt.tzinfo is not None:
        utc_dt = dt.astimezone(timezone.utc)
        return utc_dt.replace(tzinfo=None)
    else:
        return dt


async def fetch_race_control_events_from_openf1(session_key: int) -> List[F1RaceControlEvent]:
    """
    Fetch race control events from OpenF1 API.
    Raises HTTPException if API returns empty response.
    """
    parameters = {"session_key": session_key}
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(RACE_CONTROL_API_URL, params=parameters)
            response.raise_for_status()
            
            json_data = response.json()
            if not json_data:
                logger.warning("OpenF1 API returned empty race control events for session_key=%s", session_key)
                # Empty is OK for race control events, return empty list
                return []
            
            events = [F1RaceControlEvent(**event) for event in json_data]
            logger.info("Fetched %d race control events from OpenF1 for session_key=%s", len(events), session_key)
            return events
    except Exception as e:
        logger.exception("Error fetching race control events from OpenF1 API for session_key=%s", session_key)
        raise e


def convert_openf1_to_db_model(openf1_event: F1RaceControlEvent) -> RaceControlEventDB:
    """
    Convert OpenF1 API race control event model to database model.
    Handles timezone conversion for datetime fields.
    """
    # Determine scope if not explicitly provided
    scope = openf1_event.scope
    if not scope:
        if openf1_event.driver_number is not None:
            scope = "Driver"
        elif openf1_event.sector is not None:
            scope = "Sector"
        else:
            scope = "Track"
    
    return RaceControlEventDB(
        meeting_key=openf1_event.meeting_key,
        session_key=openf1_event.session_key,
        date=normalize_datetime(openf1_event.date),
        category=openf1_event.category or "Other",
        message=openf1_event.message,
        scope=scope,
        sector=openf1_event.sector,
        driver_number=openf1_event.driver_number,
        flag=openf1_event.flag
    )


def convert_db_to_response_model(db_event: RaceControlEventDB) -> RaceControlEventResponse:
    """
    Convert database model to API response model.
    """
    return RaceControlEventResponse(
        session_key=db_event.session_key,
        date=db_event.date.isoformat() if isinstance(db_event.date, datetime) else str(db_event.date),
        category=db_event.category,
        message=db_event.message,
        scope=db_event.scope,
        sector=db_event.sector,
        driver_number=db_event.driver_number,
        flag=db_event.flag
    )


async def get_race_control_events_for_session(session_key: int) -> List[RaceControlEventResponse]:
    """
    Main function to get race control events for a session.
    Implements cache-first strategy: check DB first, then fetch from API if needed.
    """
    # Check if events exist in database
    events_exist = await check_race_control_events_exists(session_key)
    
    if events_exist:
        logger.info("Race control events served from DB cache for session_key=%s", session_key)
        db_events = await get_race_control_events_from_db(session_key)
    else:
        # Fetch from OpenF1 API
        logger.info("Race control events not found in DB. Fetching from OpenF1 for session_key=%s", session_key)
        openf1_events = await fetch_race_control_events_from_openf1(session_key)
        
        # Convert to DB models
        db_event_models = [convert_openf1_to_db_model(event) for event in openf1_events]
        
        # Store in database (batch insert)
        if db_event_models:
            logger.info("Inserting %d race control events into database for session_key=%s", len(db_event_models), session_key)
            await insert_race_control_events_batch(db_event_models)
        
        # Fetch from database to ensure consistency
        db_events = await get_race_control_events_from_db(session_key)
    
    # Convert to response model
    return [convert_db_to_response_model(event) for event in db_events]

