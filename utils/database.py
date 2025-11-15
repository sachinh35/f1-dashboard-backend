"""
Database utility functions for PostgreSQL operations.
Handles connection management and common database operations.
"""
import asyncpg
from typing import List, Optional
from contextlib import asynccontextmanager
from config.database_config import DatabaseConfig
from api_pydantic_models.lap_data import LapDataDB


class DatabaseManager:
    """Manager class for database connections and operations."""
    
    _pool: Optional[asyncpg.Pool] = None
    
    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        """
        Get or create a connection pool.
        Uses singleton pattern to reuse the same pool across requests.
        """
        if cls._pool is None:
            connection_string = DatabaseConfig.get_async_connection_string()
            cls._pool = await asyncpg.create_pool(
                connection_string,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
        return cls._pool
    
    @classmethod
    async def close_pool(cls):
        """Close the database connection pool."""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
    
    @classmethod
    @asynccontextmanager
    async def get_connection(cls):
        """
        Context manager for database connections.
        Automatically returns connection to pool when done.
        """
        pool = await cls.get_pool()
        async with pool.acquire() as connection:
            yield connection


async def check_session_data_exists(session_key: int, driver_numbers: List[int]) -> bool:
    """
    Check if lap data exists in database for given session and drivers.
    
    Args:
        session_key: Session identifier
        driver_numbers: List of driver numbers to check
        
    Returns:
        True if data exists for all drivers, False otherwise
    """
    async with DatabaseManager.get_connection() as conn:
        query = """
            SELECT COUNT(DISTINCT driver_number) as driver_count
            FROM lap_data
            WHERE session_key = $1 AND driver_number = ANY($2::int[])
        """
        result = await conn.fetchval(query, session_key, driver_numbers)
        return result == len(driver_numbers)


async def get_lap_data_from_db(
    session_key: int, 
    driver_numbers: List[int]
) -> List[LapDataDB]:
    """
    Retrieve lap data from database for given session and drivers.
    
    Args:
        session_key: Session identifier
        driver_numbers: List of driver numbers to fetch
        
    Returns:
        List of LapDataDB objects sorted by driver_number and lap_number
    """
    async with DatabaseManager.get_connection() as conn:
        query = """
            SELECT 
                id, meeting_key, session_key, driver_number, lap_number,
                date_start, duration_sector_1, duration_sector_2, duration_sector_3,
                lap_duration, i1_speed, i2_speed, st_speed, is_pit_out_lap,
                segments_sector_1, segments_sector_2, segments_sector_3,
                created_at, updated_at
            FROM lap_data
            WHERE session_key = $1 AND driver_number = ANY($2::int[])
            ORDER BY driver_number, lap_number
        """
        rows = await conn.fetch(query, session_key, driver_numbers)
        
        return [
            LapDataDB(
                id=row['id'],
                meeting_key=row['meeting_key'],
                session_key=row['session_key'],
                driver_number=row['driver_number'],
                lap_number=row['lap_number'],
                date_start=row['date_start'],
                duration_sector_1=row['duration_sector_1'],
                duration_sector_2=row['duration_sector_2'],
                duration_sector_3=row['duration_sector_3'],
                lap_duration=row['lap_duration'],
                i1_speed=row['i1_speed'],
                i2_speed=row['i2_speed'],
                st_speed=row['st_speed'],
                is_pit_out_lap=row['is_pit_out_lap'],
                segments_sector_1=row['segments_sector_1'],
                segments_sector_2=row['segments_sector_2'],
                segments_sector_3=row['segments_sector_3'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            for row in rows
        ]


async def insert_lap_data_batch(lap_data_list: List[LapDataDB]) -> None:
    """
    Insert multiple lap data records into database using batch insert.
    Uses ON CONFLICT to handle duplicates gracefully.
    
    Args:
        lap_data_list: List of LapDataDB objects to insert
    """
    if not lap_data_list:
        return
    
    async with DatabaseManager.get_connection() as conn:
        # Prepare batch insert with ON CONFLICT handling
        query = """
            INSERT INTO lap_data (
                meeting_key, session_key, driver_number, lap_number,
                date_start, duration_sector_1, duration_sector_2, duration_sector_3,
                lap_duration, i1_speed, i2_speed, st_speed, is_pit_out_lap,
                segments_sector_1, segments_sector_2, segments_sector_3
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16
            )
            ON CONFLICT (session_key, driver_number, lap_number) 
            DO UPDATE SET
                meeting_key = EXCLUDED.meeting_key,
                date_start = EXCLUDED.date_start,
                duration_sector_1 = EXCLUDED.duration_sector_1,
                duration_sector_2 = EXCLUDED.duration_sector_2,
                duration_sector_3 = EXCLUDED.duration_sector_3,
                lap_duration = EXCLUDED.lap_duration,
                i1_speed = EXCLUDED.i1_speed,
                i2_speed = EXCLUDED.i2_speed,
                st_speed = EXCLUDED.st_speed,
                is_pit_out_lap = EXCLUDED.is_pit_out_lap,
                segments_sector_1 = EXCLUDED.segments_sector_1,
                segments_sector_2 = EXCLUDED.segments_sector_2,
                segments_sector_3 = EXCLUDED.segments_sector_3,
                updated_at = CURRENT_TIMESTAMP
        """
        
        # Execute batch insert
        await conn.executemany(
            query,
            [
                (
                    lap.meeting_key, lap.session_key, lap.driver_number, lap.lap_number,
                    lap.date_start, lap.duration_sector_1, lap.duration_sector_2, lap.duration_sector_3,
                    lap.lap_duration, lap.i1_speed, lap.i2_speed, lap.st_speed, lap.is_pit_out_lap,
                    lap.segments_sector_1, lap.segments_sector_2, lap.segments_sector_3
                )
                for lap in lap_data_list
            ]
        )

