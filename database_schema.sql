-- F1 Lap Data Table Schema
-- This table stores per-lap telemetry data from F1 sessions

CREATE TABLE lap_data (
    id SERIAL PRIMARY KEY,
    meeting_key INTEGER NOT NULL,
    session_key INTEGER NOT NULL,
    driver_number INTEGER NOT NULL,
    lap_number INTEGER NOT NULL,
    date_start TIMESTAMP,
    duration_sector_1 DECIMAL(10, 3),
    duration_sector_2 DECIMAL(10, 3),
    duration_sector_3 DECIMAL(10, 3),
    lap_duration DECIMAL(10, 3),
    i1_speed INTEGER,
    i2_speed INTEGER,
    st_speed INTEGER,
    is_pit_out_lap BOOLEAN DEFAULT FALSE,
    segments_sector_1 INTEGER[],
    segments_sector_2 INTEGER[],
    segments_sector_3 INTEGER[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure we don't store duplicate laps for the same session/driver
    CONSTRAINT unique_lap_per_driver_session 
        UNIQUE(session_key, driver_number, lap_number)
);

-- Index for primary query pattern: get all laps for a session/driver combo
CREATE INDEX idx_session_driver_lap 
    ON lap_data(session_key, driver_number, lap_number);

-- Index for session lookups (useful for checking if session data exists)
CREATE INDEX idx_session_key 
    ON lap_data(session_key);

-- Index for meeting key lookups (if needed later)
CREATE INDEX idx_meeting_key 
    ON lap_data(meeting_key);

-- Index for driver number queries across sessions
CREATE INDEX idx_driver_number 
    ON lap_data(driver_number);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to update updated_at on row updates
CREATE TRIGGER update_lap_data_updated_at 
    BEFORE UPDATE ON lap_data
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

