with source_data as (

    select *
    from {{ source('stockpilot_raw', 'companies') }}

),

cleaned as (

    select
        tenant_id,
        trim(company_name) as company_name,
        nullif(trim(industry), '') as industry,
        coalesce(
            nullif(trim(country), ''),
            'Morocco'
        ) as country,
        created_at,
        updated_at

    from source_data

)

select *
from cleaned