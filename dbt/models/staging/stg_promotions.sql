with source_data as (

    select *
    from {{ source('stockpilot_raw', 'promotions') }}

),

cleaned as (

    select
        promotion_id,
        tenant_id,
        product_id,
        store_id,
        start_date,
        end_date,
        discount_percentage,

        end_date - start_date + 1
            as promotion_duration_days,

        case
            when current_date between start_date and end_date
                then true
            else false
        end as is_currently_active,

        imported_at

    from source_data

)

select *
from cleaned