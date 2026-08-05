with stores as (

    select *
    from {{ ref('stg_stores') }}

),

final as (

    select
        store_id,
        tenant_id,
        store_code,
        store_name,
        city,
        region,
        active,
        created_at

    from stores

)

select *
from final