with source_data as (

    select *
    from {{ source('stockpilot_raw', 'inventory') }}

),

cleaned as (

    select
        inventory_id,
        tenant_id,
        inventory_date,
        store_id,
        product_id,
        stock_on_hand,
        quantity_on_order,
        backorders,

        stock_on_hand
        + quantity_on_order
        - backorders
            as inventory_position,

        case
            when stock_on_hand = 0 then true
            else false
        end as is_out_of_stock,

        case
            when backorders > 0 then true
            else false
        end as has_backorders,

        imported_at

    from source_data

)

select *
from cleaned