"""
Utility functions for fetching and managing stints data.
Cache-first: check DB, otherwise fetch from OpenF1 API and store.
"""
from typing import List
import httpx
from constants.openf1_api_endpoints import STINTS_API_URL
from openf1_pydantic_models.f1_stints import F1Stint
from api_pydantic_models.stints import StintDB, StintResponse
from utils.database import (
    check_session_stints_exists,
    get_stints_from_db,
    insert_stints_batch
)
import logging

logger = logging.getLogger(__name__)


async def fetch_stints_from_openf1(session_key: int) -> List[F1Stint]:
    params = {"session_key": session_key}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(STINTS_API_URL, params=params)
        resp.raise_for_status()
        items = [F1Stint(**item) for item in resp.json()]
        logger.info("Fetched %d stints from OpenF1 for session_key=%s", len(items), session_key)
        return items


def convert_openf1_to_db_model(openf1: F1Stint) -> StintDB:
    return StintDB(
        meeting_key=openf1.meeting_key,
        session_key=openf1.session_key,
        driver_number=openf1.driver_number,
        stint_number=openf1.stint_number,
        lap_start=openf1.lap_start,
        lap_end=openf1.lap_end,
        compound=openf1.compound,
        tyre_age_at_start=openf1.tyre_age_at_start
    )


def convert_db_to_response_model(db: StintDB) -> StintResponse:
    return StintResponse(
        meeting_key=db.meeting_key,
        session_key=db.session_key,
        driver_number=db.driver_number,
        stint_number=db.stint_number,
        lap_start=db.lap_start,
        lap_end=db.lap_end,
        compound=db.compound,
        tyre_age_at_start=db.tyre_age_at_start
    )


async def get_stints_for_session(session_key: int) -> List[StintResponse]:
    # Check if stints already in DB
    exists = await check_session_stints_exists(session_key)
    if exists:
        logger.info("Stints served from DB cache for session_key=%s", session_key)
        db_rows = await get_stints_from_db(session_key)
    else:
        # Fetch from API and store
        logger.info("Stints not found in DB. Fetching from OpenF1 for session_key=%s", session_key)
        openf1_stints = await fetch_stints_from_openf1(session_key)
        models = [convert_openf1_to_db_model(s) for s in openf1_stints]
        if models:
            logger.info("Inserting %d stints into DB for session_key=%s", len(models), session_key)
            await insert_stints_batch(models)
        db_rows = await get_stints_from_db(session_key)
        logger.info("Stints served after OpenF1 fetch for session_key=%s", session_key)
    return [convert_db_to_response_model(r) for r in db_rows]


