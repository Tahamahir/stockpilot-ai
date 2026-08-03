-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- StockPilot data layers
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS ml;

-- Temporary table used to validate the installation
CREATE TABLE IF NOT EXISTS raw.pipeline_test (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO raw.pipeline_test (message)
VALUES ('StockPilot PostgreSQL installation successful');