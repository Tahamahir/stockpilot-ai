CREATE TABLE IF NOT EXISTS ml.replenishment_recommendations (
    recommendation_id UUID PRIMARY KEY,

    forecast_run_id UUID NOT NULL
        REFERENCES ml.forecast_runs(forecast_run_id)
        ON DELETE CASCADE,

    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    tenant_id UUID NOT NULL,
    store_id UUID NOT NULL,
    product_id UUID NOT NULL,

    forecast_30d DOUBLE PRECISION NOT NULL,
    forecast_lead_time DOUBLE PRECISION NOT NULL,

    lead_time_days INTEGER NOT NULL,

    safety_stock_units DOUBLE PRECISION NOT NULL,

    stock_on_hand DOUBLE PRECISION NOT NULL,
    quantity_on_order DOUBLE PRECISION NOT NULL,
    backorders DOUBLE PRECISION NOT NULL,
    inventory_position DOUBLE PRECISION NOT NULL,

    target_stock_units DOUBLE PRECISION NOT NULL,
    net_requirement_units DOUBLE PRECISION NOT NULL,

    minimum_order_quantity DOUBLE PRECISION NOT NULL,
    package_size DOUBLE PRECISION NOT NULL,

    recommended_order_quantity DOUBLE PRECISION NOT NULL,

    estimated_stockout_date DATE,

    urgency_level TEXT NOT NULL,

    UNIQUE (
        forecast_run_id,
        store_id,
        product_id
    )
);


CREATE INDEX IF NOT EXISTS
idx_ml_replenishment_priority
ON ml.replenishment_recommendations (
    urgency_level,
    recommended_order_quantity DESC
);