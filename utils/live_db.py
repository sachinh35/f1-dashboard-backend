from typing import List, Optional
from pydantic import BaseModel
from utils.database import DatabaseManager
from datetime import datetime

class LiveStreamDB(BaseModel):
    id: int
    stream_id: str
    race_name: Optional[str]
    start_time: datetime
    created_at: datetime

class LiveLapTimeDB(BaseModel):
    id: Optional[int] = None
    stream_id: str
    driver_number: int
    lap_number: int
    lap_time: Optional[float]
    sector_1: Optional[float]
    sector_2: Optional[float]
    sector_3: Optional[float]
    created_at: Optional[datetime] = None

async def create_live_stream(stream_id: str, race_name: str) -> int:
    """Create a new live stream entry."""
    async with DatabaseManager.get_connection() as conn:
        query = """
            INSERT INTO live_streams (stream_id, race_name)
            VALUES ($1, $2)
            ON CONFLICT (stream_id) DO UPDATE 
            SET race_name = EXCLUDED.race_name
            RETURNING id
        """
        return await conn.fetchval(query, stream_id, race_name)

async def insert_live_lap_time(lap_time: LiveLapTimeDB) -> None:
    """Insert a live lap time record."""
    async with DatabaseManager.get_connection() as conn:
        query = """
            INSERT INTO live_lap_times (
                stream_id, driver_number, lap_number, 
                lap_time, sector_1, sector_2, sector_3
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (stream_id, driver_number, lap_number) 
            DO UPDATE SET
                lap_time = EXCLUDED.lap_time,
                sector_1 = EXCLUDED.sector_1,
                sector_2 = EXCLUDED.sector_2,
                sector_3 = EXCLUDED.sector_3
        """
        await conn.execute(
            query,
            lap_time.stream_id,
            lap_time.driver_number,
            lap_time.lap_number,
            lap_time.lap_time,
            lap_time.sector_1,
            lap_time.sector_2,
            lap_time.sector_3
        )

async def get_live_lap_times(stream_id: str) -> List[LiveLapTimeDB]:
    """Fetch all lap times for a given stream."""
    async with DatabaseManager.get_connection() as conn:
        query = """
            SELECT 
                id, stream_id, driver_number, lap_number,
                lap_time, sector_1, sector_2, sector_3,
                created_at
            FROM live_lap_times
            WHERE stream_id = $1
            ORDER BY lap_number, driver_number
        """
        rows = await conn.fetch(query, stream_id)
        return [
            LiveLapTimeDB(
                id=row['id'],
                stream_id=row['stream_id'],
                driver_number=row['driver_number'],
                lap_number=row['lap_number'],
                lap_time=float(row['lap_time']) if row['lap_time'] is not None else None,
                sector_1=float(row['sector_1']) if row['sector_1'] is not None else None,
                sector_2=float(row['sector_2']) if row['sector_2'] is not None else None,
                sector_3=float(row['sector_3']) if row['sector_3'] is not None else None,
                created_at=row['created_at']
            )
            for row in rows
        ]
