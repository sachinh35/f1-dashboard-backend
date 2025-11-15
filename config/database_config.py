"""
Database configuration for PostgreSQL connection.
Centralized configuration to allow easy changes for Docker/deployment.
"""
import os
from typing import Optional


class DatabaseConfig:
    """Database configuration class with environment variable support."""
    
    DB_USER: str = os.getenv("DB_USER", "sachinh")
    DB_NAME: str = os.getenv("DB_NAME", "f1-analytics")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_PASSWORD: Optional[str] = os.getenv("DB_PASSWORD", None)
    
    @classmethod
    def get_connection_string(cls) -> str:
        """
        Get PostgreSQL connection string.
        Uses password from environment if available, otherwise assumes no password.
        """
        if cls.DB_PASSWORD:
            return f"postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
        else:
            return f"postgresql://{cls.DB_USER}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
    
    @classmethod
    def get_async_connection_params(cls) -> dict:
        """
        Get PostgreSQL async connection parameters for asyncpg.
        Returns dict with connection parameters instead of connection string.
        """
        params = {
            "host": cls.DB_HOST,
            "port": cls.DB_PORT,
            "database": cls.DB_NAME,
            "user": cls.DB_USER,
        }
        if cls.DB_PASSWORD:
            params["password"] = cls.DB_PASSWORD
        return params
    
    @classmethod
    def get_async_connection_string(cls) -> str:
        """
        Get PostgreSQL async connection string for asyncpg.
        Uses password from environment if available, otherwise assumes no password.
        """
        if cls.DB_PASSWORD:
            return f"postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
        else:
            return f"postgresql://{cls.DB_USER}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"

