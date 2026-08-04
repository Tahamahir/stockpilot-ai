with inventory as (

    select *
    from {{ ref('stg_inventory') }}

),

with_previous_values as (

    select
        inventory_id,
        tenant_id,
        inventory_date,
        store_id,
        product_id,
        stock_on_hand,
        quantity_on_order,
        backorders,
        inventory_position,
        is_out_of_stock,
        has_backorders,
        imported_at,

        lag(stock_on_hand) over (
            partition by
                tenant_id,
                store_id,
                product_id
            order by inventory_date
        ) as previous_stock_on_hand,

        lag(quantity_on_order) over (
            partition by
                tenant_id,
                store_id,
                product_id
            order by inventory_date
        ) as previous_quantity_on_order,

        lag(backorders) over (
            partition by
                tenant_id,
                store_id,
                product_id
            order by inventory_date
        ) as previous_backorders

    from inventory

),

movements as (

    select
        inventory_id,
        tenant_id,
        inventory_date,
        store_id,
        product_id,
        stock_on_hand,
        quantity_on_order,
        backorders,
        inventory_position,

        previous_stock_on_hand,
        previous_quantity_on_order,
        previous_backorders,

        case
            when previous_stock_on_hand is null
                then null
            else stock_on_hand - previous_stock_on_hand
        end as stock_change,

        case
            when previous_quantity_on_order is null
                then null
            else quantity_on_order
                - previous_quantity_on_order
        end as quantity_on_order_change,

        case
            when previous_backorders is null
                then null
            else backorders - previous_backorders
        end as backorders_change,

        case
            when previous_stock_on_hand is not null
                and stock_on_hand > previous_stock_on_hand
                then true
            else false
        end as is_stock_increase,

        case
            when previous_stock_on_hand is not null
                and stock_on_hand < previous_stock_on_hand
                then true
            else false
        end as is_stock_decrease,

        case
            when previous_stock_on_hand is not null
                and previous_stock_on_hand > 0
                and stock_on_hand = 0
                then true
            else false
        end as is_new_stockout,

        case
            when previous_stock_on_hand is not null
                and previous_stock_on_hand = 0
                and stock_on_hand > 0
                then true
            else false
        end as is_restocked,

        is_out_of_stock,
        has_backorders,
        imported_at

    from with_previous_values

)

select *
from movements