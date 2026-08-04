with source_data as (

    select *
    from {{ source('stockpilot_raw', 'purchase_orders') }}

),

cleaned as (

    select
        purchase_order_id,
        tenant_id,
        supplier_id,
        product_id,
        store_id,
        order_date,
        expected_delivery_date,
        actual_delivery_date,
        ordered_quantity,
        received_quantity,
        lower(trim(status)) as status,

        ordered_quantity
        - received_quantity
            as remaining_quantity,

        expected_delivery_date
        - order_date
            as expected_lead_time_days,

        case
            when actual_delivery_date is not null
                then actual_delivery_date - order_date
            else null
        end as actual_lead_time_days,

        case
            when actual_delivery_date is not null
                then actual_delivery_date
                     - expected_delivery_date
            else null
        end as delivery_delay_days,

        case
            when received_quantity = 0 then 0
            else round(
                received_quantity::numeric
                / ordered_quantity::numeric
                * 100,
                2
            )
        end as received_percentage,

        imported_at

    from source_data

)

select *
from cleaned