BEGIN;

-- =========================================================
-- COMPANY
-- =========================================================

INSERT INTO raw.companies (
    tenant_id,
    company_name,
    industry,
    country
)
VALUES (
    '11111111-1111-1111-1111-111111111111',
    'StockPilot Demo Store',
    'Retail',
    'Morocco'
)
ON CONFLICT (tenant_id) DO NOTHING;

-- =========================================================
-- STORE
-- =========================================================

INSERT INTO raw.stores (
    store_id,
    tenant_id,
    store_code,
    store_name,
    city,
    region
)
VALUES (
    '22222222-2222-2222-2222-222222222222',
    '11111111-1111-1111-1111-111111111111',
    'STORE-001',
    'Magasin Casablanca',
    'Casablanca',
    'Casablanca-Settat'
)
ON CONFLICT (store_id) DO NOTHING;

-- =========================================================
-- SUPPLIER
-- =========================================================

INSERT INTO raw.suppliers (
    supplier_id,
    tenant_id,
    supplier_code,
    supplier_name,
    average_lead_time_days,
    minimum_order_value
)
VALUES (
    '33333333-3333-3333-3333-333333333333',
    '11111111-1111-1111-1111-111111111111',
    'SUP-001',
    'Fournisseur Principal',
    7,
    500.00
)
ON CONFLICT (supplier_id) DO NOTHING;

-- =========================================================
-- PRODUCTS
-- =========================================================

INSERT INTO raw.products (
    product_id,
    tenant_id,
    supplier_id,
    sku,
    product_name,
    category_name,
    purchase_price,
    selling_price,
    lead_time_days,
    minimum_order_quantity,
    package_size
)
VALUES
(
    '44444444-4444-4444-4444-444444444444',
    '11111111-1111-1111-1111-111111111111',
    '33333333-3333-3333-3333-333333333333',
    'SKU-001',
    'Produit A',
    'Catégorie 1',
    50.00,
    75.00,
    7,
    10,
    5
),
(
    '55555555-5555-5555-5555-555555555555',
    '11111111-1111-1111-1111-111111111111',
    '33333333-3333-3333-3333-333333333333',
    'SKU-002',
    'Produit B',
    'Catégorie 1',
    30.00,
    45.00,
    5,
    20,
    10
),
(
    '66666666-6666-6666-6666-666666666666',
    '11111111-1111-1111-1111-111111111111',
    '33333333-3333-3333-3333-333333333333',
    'SKU-003',
    'Produit C',
    'Catégorie 2',
    80.00,
    120.00,
    10,
    5,
    1
)
ON CONFLICT (product_id) DO NOTHING;

-- =========================================================
-- SALES
-- =========================================================

INSERT INTO raw.sales (
    tenant_id,
    sale_reference,
    sale_date,
    store_id,
    product_id,
    quantity,
    unit_price,
    discount_percentage,
    total_amount
)
VALUES
(
    '11111111-1111-1111-1111-111111111111',
    'SALE-001',
    CURRENT_DATE - 3,
    '22222222-2222-2222-2222-222222222222',
    '44444444-4444-4444-4444-444444444444',
    4,
    75.00,
    0,
    300.00
),
(
    '11111111-1111-1111-1111-111111111111',
    'SALE-002',
    CURRENT_DATE - 2,
    '22222222-2222-2222-2222-222222222222',
    '55555555-5555-5555-5555-555555555555',
    10,
    45.00,
    0,
    450.00
),
(
    '11111111-1111-1111-1111-111111111111',
    'SALE-003',
    CURRENT_DATE - 1,
    '22222222-2222-2222-2222-222222222222',
    '66666666-6666-6666-6666-666666666666',
    2,
    120.00,
    10,
    216.00
)
ON CONFLICT (tenant_id, sale_reference) DO NOTHING;

-- =========================================================
-- INVENTORY
-- =========================================================

INSERT INTO raw.inventory (
    tenant_id,
    inventory_date,
    store_id,
    product_id,
    stock_on_hand,
    quantity_on_order,
    backorders
)
VALUES
(
    '11111111-1111-1111-1111-111111111111',
    CURRENT_DATE,
    '22222222-2222-2222-2222-222222222222',
    '44444444-4444-4444-4444-444444444444',
    15,
    20,
    3
),
(
    '11111111-1111-1111-1111-111111111111',
    CURRENT_DATE,
    '22222222-2222-2222-2222-222222222222',
    '55555555-5555-5555-5555-555555555555',
    100,
    0,
    0
),
(
    '11111111-1111-1111-1111-111111111111',
    CURRENT_DATE,
    '22222222-2222-2222-2222-222222222222',
    '66666666-6666-6666-6666-666666666666',
    5,
    10,
    2
)
ON CONFLICT (
    tenant_id,
    inventory_date,
    store_id,
    product_id
) DO NOTHING;

COMMIT;