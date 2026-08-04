with source_data as (

    select *
    from {{ source('stockpilot_raw', 'stores') }}

),

cleaned as (

    select
        store_id,
        tenant_id,
        upper(trim(store_code)) as store_code,
        trim(store_name) as store_name,
        nullif(trim(city), '') as city,
        nullif(trim(region), '') as region,
        active,
        created_at

    from source_data

)

select *
from cleaned