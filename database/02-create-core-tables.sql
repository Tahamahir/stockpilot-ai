BEGIN;

-- =========================================================
-- 1. COMPANIES
-- =========================================================

CREATE TABLE IF NOT EXISTS raw.companies (
    tenant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(150) NOT NULL,
    industry VARCHAR(100),
    country VARCHAR(100) NOT NULL DEFAULT 'Morocco',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- 2. STORES
-- =========================================================

CREATE TABLE IF NOT EXISTS raw.stores (
    store_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    store_code VARCHAR(50) NOT NULL,
    store_name VARCHAR(150) NOT NULL,
    city VARCHAR(100),
    region VARCHAR(100),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_stores_company
        FOREIGN KEY (tenant_id)
        REFERENCES raw.companies (tenant_id)
        ON DELETE CASCADE,

    CONSTRAINT uq_stores_tenant_code
        UNIQUE (tenant_id, store_code),

    CONSTRAINT uq_stores_tenant_id_store_id
        UNIQUE (tenant_id, store_id)
);

-- =========================================================
-- 3. SUPPLIERS
-- =========================================================

CREATE TABLE IF NOT EXISTS raw.suppliers (
    supplier_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    supplier_code VARCHAR(50) NOT NULL,
    supplier_name VARCHAR(150) NOT NULL,
    average_lead_time_days INTEGER NOT NULL DEFAULT 7,
    minimum_order_value NUMERIC(12, 2) NOT NULL DEFAULT 0,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_suppliers_company
        FOREIGN KEY (tenant_id)
        REFERENCES raw.companies (tenant_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_supplier_lead_time
        CHECK (average_lead_time_days >= 0),

    CONSTRAINT chk_supplier_minimum_order
        CHECK (minimum_order_value >= 0),

    CONSTRAINT uq_suppliers_tenant_code
        UNIQUE (tenant_id, supplier_code),

    CONSTRAINT uq_suppliers_tenant_id_supplier_id
        UNIQUE (tenant_id, supplier_id)
);

-- =========================================================
-- 4. PRODUCTS
-- =========================================================

CREATE TABLE IF NOT EXISTS raw.products (
    product_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    supplier_id UUID,
    sku VARCHAR(80) NOT NULL,
    product_name VARCHAR(200) NOT NULL,
    category_name VARCHAR(100),
    purchase_price NUMERIC(12, 2) NOT NULL,
    selling_price NUMERIC(12, 2) NOT NULL,
    lead_time_days INTEGER NOT NULL DEFAULT 7,
    minimum_order_quantity INTEGER NOT NULL DEFAULT 1,
    package_size INTEGER NOT NULL DEFAULT 1,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_products_company
        FOREIGN KEY (tenant_id)
        REFERENCES raw.companies (tenant_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_products_supplier
        FOREIGN KEY (tenant_id, supplier_id)
        REFERENCES raw.suppliers (tenant_id, supplier_id),

    CONSTRAINT chk_product_purchase_price
        CHECK (purchase_price >= 0),

    CONSTRAINT chk_product_selling_price
        CHECK (selling_price >= 0),

    CONSTRAINT chk_product_lead_time
        CHECK (lead_time_days >= 0),

    CONSTRAINT chk_product_minimum_order_quantity
        CHECK (minimum_order_quantity > 0),

    CONSTRAINT chk_product_package_size
        CHECK (package_size > 0),

    CONSTRAINT uq_products_tenant_sku
        UNIQUE (tenant_id, sku),

    CONSTRAINT uq_products_tenant_id_product_id
        UNIQUE (tenant_id, product_id)
);

-- =========================================================
-- 5. SALES
-- =========================================================

CREATE TABLE IF NOT EXISTS raw.sales (
    sale_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    sale_reference VARCHAR(100),
    sale_date DATE NOT NULL,
    store_id UUID NOT NULL,
    product_id UUID NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL,
    discount_percentage NUMERIC(5, 2) NOT NULL DEFAULT 0,
    total_amount NUMERIC(14, 2) NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_sales_company
        FOREIGN KEY (tenant_id)
        REFERENCES raw.companies (tenant_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_sales_store
        FOREIGN KEY (tenant_id, store_id)
        REFERENCES raw.stores (tenant_id, store_id),

    CONSTRAINT fk_sales_product
        FOREIGN KEY (tenant_id, product_id)
        REFERENCES raw.products (tenant_id, product_id),

    CONSTRAINT chk_sales_quantity
        CHECK (quantity > 0),

    CONSTRAINT chk_sales_unit_price
        CHECK (unit_price >= 0),

    CONSTRAINT chk_sales_discount
        CHECK (
            discount_percentage >= 0
            AND discount_percentage <= 100
        ),

    CONSTRAINT chk_sales_total_amount
        CHECK (total_amount >= 0),

    CONSTRAINT uq_sales_tenant_reference
        UNIQUE (tenant_id, sale_reference)
);

-- =========================================================
-- 6. INVENTORY
-- =========================================================

CREATE TABLE IF NOT EXISTS raw.inventory (
    inventory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    inventory_date DATE NOT NULL,
    store_id UUID NOT NULL,
    product_id UUID NOT NULL,
    stock_on_hand INTEGER NOT NULL DEFAULT 0,
    quantity_on_order INTEGER NOT NULL DEFAULT 0,
    backorders INTEGER NOT NULL DEFAULT 0,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_inventory_company
        FOREIGN KEY (tenant_id)
        REFERENCES raw.companies (tenant_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_inventory_store
        FOREIGN KEY (tenant_id, store_id)
        REFERENCES raw.stores (tenant_id, store_id),

    CONSTRAINT fk_inventory_product
        FOREIGN KEY (tenant_id, product_id)
        REFERENCES raw.products (tenant_id, product_id),

    CONSTRAINT chk_inventory_stock_on_hand
        CHECK (stock_on_hand >= 0),

    CONSTRAINT chk_inventory_quantity_on_order
        CHECK (quantity_on_order >= 0),

    CONSTRAINT chk_inventory_backorders
        CHECK (backorders >= 0),

    CONSTRAINT uq_inventory_snapshot
        UNIQUE (
            tenant_id,
            inventory_date,
            store_id,
            product_id
        )
);

-- =========================================================
-- INDEXES
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_sales_tenant_date
    ON raw.sales (tenant_id, sale_date);

CREATE INDEX IF NOT EXISTS idx_sales_product_date
    ON raw.sales (product_id, sale_date);

CREATE INDEX IF NOT EXISTS idx_sales_store_date
    ON raw.sales (store_id, sale_date);

CREATE INDEX IF NOT EXISTS idx_inventory_tenant_date
    ON raw.inventory (tenant_id, inventory_date);

CREATE INDEX IF NOT EXISTS idx_inventory_product_date
    ON raw.inventory (product_id, inventory_date);

CREATE INDEX IF NOT EXISTS idx_products_supplier
    ON raw.products (supplier_id);

COMMIT;