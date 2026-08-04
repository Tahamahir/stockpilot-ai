BEGIN;

-- =========================================================
-- 1. PROMOTIONS
-- =========================================================

CREATE TABLE IF NOT EXISTS raw.promotions (
    promotion_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    product_id UUID NOT NULL,
    store_id UUID NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    discount_percentage NUMERIC(5, 2) NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_promotions_company
        FOREIGN KEY (tenant_id)
        REFERENCES raw.companies (tenant_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_promotions_product
        FOREIGN KEY (tenant_id, product_id)
        REFERENCES raw.products (tenant_id, product_id),

    CONSTRAINT fk_promotions_store
        FOREIGN KEY (tenant_id, store_id)
        REFERENCES raw.stores (tenant_id, store_id),

    CONSTRAINT chk_promotions_dates
        CHECK (end_date >= start_date),

    CONSTRAINT chk_promotions_discount
        CHECK (
            discount_percentage > 0
            AND discount_percentage <= 100
        )
);

-- =========================================================
-- 2. PURCHASE ORDERS
-- =========================================================

CREATE TABLE IF NOT EXISTS raw.purchase_orders (
    purchase_order_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    supplier_id UUID NOT NULL,
    product_id UUID NOT NULL,
    store_id UUID NOT NULL,
    order_date DATE NOT NULL,
    expected_delivery_date DATE NOT NULL,
    actual_delivery_date DATE,
    ordered_quantity INTEGER NOT NULL,
    received_quantity INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_purchase_orders_company
        FOREIGN KEY (tenant_id)
        REFERENCES raw.companies (tenant_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_purchase_orders_supplier
        FOREIGN KEY (tenant_id, supplier_id)
        REFERENCES raw.suppliers (tenant_id, supplier_id),

    CONSTRAINT fk_purchase_orders_product
        FOREIGN KEY (tenant_id, product_id)
        REFERENCES raw.products (tenant_id, product_id),

    CONSTRAINT fk_purchase_orders_store
        FOREIGN KEY (tenant_id, store_id)
        REFERENCES raw.stores (tenant_id, store_id),

    CONSTRAINT chk_purchase_orders_ordered_quantity
        CHECK (ordered_quantity > 0),

    CONSTRAINT chk_purchase_orders_received_quantity
        CHECK (received_quantity >= 0),

    CONSTRAINT chk_purchase_orders_received_limit
        CHECK (received_quantity <= ordered_quantity),

    CONSTRAINT chk_purchase_orders_expected_date
        CHECK (expected_delivery_date >= order_date),

    CONSTRAINT chk_purchase_orders_actual_date
        CHECK (
            actual_delivery_date IS NULL
            OR actual_delivery_date >= order_date
        ),

    CONSTRAINT chk_purchase_orders_status
        CHECK (
            status IN (
                'open',
                'received',
                'partially_received',
                'delayed',
                'cancelled'
            )
        )
);

-- =========================================================
-- 3. REJECTED RECORDS
-- =========================================================

CREATE TABLE IF NOT EXISTS raw.rejected_records (
    rejection_id BIGSERIAL PRIMARY KEY,
    source_file VARCHAR(255) NOT NULL,
    table_name VARCHAR(100),
    row_number INTEGER,
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    raw_record JSONB,
    dag_run_id VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- 4. INGESTION RUNS
-- =========================================================

CREATE TABLE IF NOT EXISTS raw.ingestion_runs (
    ingestion_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dag_run_id VARCHAR(255) NOT NULL,
    source_file VARCHAR(255),
    target_table VARCHAR(150),
    status VARCHAR(30) NOT NULL,
    rows_detected INTEGER NOT NULL DEFAULT 0,
    rows_loaded INTEGER NOT NULL DEFAULT 0,
    rows_rejected INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    error_message TEXT,

    CONSTRAINT chk_ingestion_runs_status
        CHECK (
            status IN (
                'started',
                'success',
                'failed',
                'partial'
            )
        ),

    CONSTRAINT chk_ingestion_rows_detected
        CHECK (rows_detected >= 0),

    CONSTRAINT chk_ingestion_rows_loaded
        CHECK (rows_loaded >= 0),

    CONSTRAINT chk_ingestion_rows_rejected
        CHECK (rows_rejected >= 0)
);

-- =========================================================
-- INDEXES
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_promotions_product_dates
    ON raw.promotions (
        tenant_id,
        product_id,
        start_date,
        end_date
    );

CREATE INDEX IF NOT EXISTS idx_promotions_store_dates
    ON raw.promotions (
        tenant_id,
        store_id,
        start_date,
        end_date
    );

CREATE INDEX IF NOT EXISTS idx_purchase_orders_product
    ON raw.purchase_orders (
        tenant_id,
        product_id,
        order_date
    );

CREATE INDEX IF NOT EXISTS idx_purchase_orders_supplier
    ON raw.purchase_orders (
        tenant_id,
        supplier_id,
        order_date
    );

CREATE INDEX IF NOT EXISTS idx_purchase_orders_status
    ON raw.purchase_orders (
        tenant_id,
        status
    );

CREATE INDEX IF NOT EXISTS idx_rejected_records_source
    ON raw.rejected_records (
        source_file,
        created_at
    );

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_dag_run
    ON raw.ingestion_runs (
        dag_run_id
    );

COMMIT;