with source_data as (

    select *
    from {{ source('stockpilot_raw', 'sales') }}

),

cleaned as (

    select
        sale_id,
        tenant_id,
        nullif(trim(sale_reference), '') as sale_reference,
        sale_date,
        store_id,
        product_id,
        quantity,
        unit_price,
        discount_percentage,
        total_amount,

        round(
            quantity
            * unit_price
            * (
                1 - discount_percentage / 100
            ),
            2
        ) as expected_total_amount,

        round(
            total_amount
            - (
                quantity
                * unit_price
                * (
                    1 - discount_percentage / 100
                )
            ),
            2
        ) as total_amount_difference,

        imported_at

    from source_data

)

select *
from cleaned