with inventory as (

    select *
    from {{ ref('int_inventory_movements') }}

),

products as (

    select *
    from {{ ref('dim_products') }}

),

final as (

    select
        md5(
            concat_ws(
                '|',
                inventory.tenant_id::text,
                inventory.inventory_date::text,
                inventory.store_id::text,
                inventory.product_id::text
            )
        ) as inventory_snapshot_key,

        inventory.inventory_id,
        inventory.tenant_id,
        inventory.inventory_date,
        inventory.store_id,
        inventory.product_id,

        products.supplier_id,
        products.sku,
        products.product_name,
        products.category_name,

        inventory.stock_on_hand,
        inventory.quantity_on_order,
        inventory.backorders,
        inventory.inventory_position,

        inventory.previous_stock_on_hand,
        inventory.previous_quantity_on_order,
        inventory.previous_backorders,

        inventory.stock_change,
        inventory.quantity_on_order_change,
        inventory.backorders_change,

        inventory.is_stock_increase,
        inventory.is_stock_decrease,
        inventory.is_new_stockout,
        inventory.is_restocked,
        inventory.is_out_of_stock,
        inventory.has_backorders,

        products.purchase_price,
        products.selling_price,

        round(
            inventory.stock_on_hand
            * products.purchase_price,
            2
        ) as stock_value_at_cost,

        round(
            inventory.stock_on_hand
            * products.selling_price,
            2
        ) as stock_value_at_retail,

        round(
            inventory.inventory_position
            * products.purchase_price,
            2
        ) as inventory_position_value_at_cost,

        inventory.imported_at

    from inventory

    inner join products
        on inventory.tenant_id = products.tenant_id
        and inventory.product_id = products.product_id

)

select *
from final