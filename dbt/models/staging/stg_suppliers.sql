with source_data as (

    select *
    from {{ source('stockpilot_raw', 'suppliers') }}

),

cleaned as (

    select
        supplier_id,
        tenant_id,
        upper(trim(supplier_code)) as supplier_code,
        trim(supplier_name) as supplier_name,
        average_lead_time_days,
        minimum_order_value,
        active,
        created_at

    from source_data

)

select *
from cleaned