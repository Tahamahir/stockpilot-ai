CREATE SCHEMA IF NOT EXISTS ml;


-- =========================================================
-- One record per forecasting execution
-- =========================================================
CREATE TABLE IF NOT EXISTS ml.forecast_runs (
    forecast_run_id UUID PRIMARY KEY,

    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    model_name TEXT NOT NULL,
    model_version INTEGER NOT NULL,
    model_alias TEXT NOT NULL,

    source_training_run_id TEXT,

    training_end_date DATE NOT NULL,

    forecast_start_date DATE NOT NULL,
    forecast_end_date DATE NOT NULL,

    horizon_days INTEGER NOT NULL
        CHECK (horizon_days > 0),

    number_of_series INTEGER NOT NULL
        CHECK (number_of_series > 0),

    status TEXT NOT NULL
        CHECK (
            status IN (
                'running',
                'completed',
                'failed'
            )
        )
);


-- =========================================================
-- Forecasted demand
-- =========================================================
CREATE TABLE IF NOT EXISTS ml.demand_forecasts (
    forecast_run_id UUID NOT NULL
        REFERENCES ml.forecast_runs(forecast_run_id)
        ON DELETE CASCADE,

    forecast_date DATE NOT NULL,

    horizon_day INTEGER NOT NULL
        CHECK (horizon_day > 0),

    tenant_id UUID NOT NULL,
    store_id UUID NOT NULL,
    product_id UUID NOT NULL,

    predicted_quantity DOUBLE PRECISION NOT NULL
        CHECK (predicted_quantity >= 0),

    PRIMARY KEY (
        forecast_run_id,
        forecast_date,
        store_id,
        product_id
    )
);


CREATE INDEX IF NOT EXISTS
idx_demand_forecasts_date
ON ml.demand_forecasts (
    forecast_date
);


CREATE INDEX IF NOT EXISTS
idx_demand_forecasts_product_store
ON ml.demand_forecasts (
    store_id,
    product_id
);


CREATE INDEX IF NOT EXISTS
idx_forecast_runs_generated_at
ON ml.forecast_runs (
    generated_at DESC
);