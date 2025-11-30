-- Live Stream Metadata Table
CREATE TABLE IF NOT EXISTS live_streams (
    id SERIAL PRIMARY KEY,
    stream_id VARCHAR(50) NOT NULL UNIQUE,
    race_name VARCHAR(255),
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Live Lap Times Table
CREATE TABLE IF NOT EXISTS live_lap_times (
    id SERIAL PRIMARY KEY,
    stream_id VARCHAR(50) NOT NULL REFERENCES live_streams(stream_id),
    driver_number INTEGER NOT NULL,
    lap_number INTEGER NOT NULL,
    lap_time DECIMAL(10, 3), -- Lap time in seconds
    sector_1 DECIMAL(10, 3),
    sector_2 DECIMAL(10, 3),
    sector_3 DECIMAL(10, 3),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure unique lap per driver per stream
    CONSTRAINT unique_live_lap_per_driver UNIQUE(stream_id, driver_number, lap_number)
);

-- Indexes for faster retrieval
CREATE INDEX IF NOT EXISTS idx_live_lap_times_stream ON live_lap_times(stream_id);
CREATE INDEX IF NOT EXISTS idx_live_lap_times_stream_driver ON live_lap_times(stream_id, driver_number);
