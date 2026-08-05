select
    inventory_health_key,
    tenant_id,
    store_id,
    product_id,
    recommended_order_quantity

from {{ ref('mart_inventory_health') }}

where recommended_order_quantity < 0