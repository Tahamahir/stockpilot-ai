with suppliers as (

    select *
    from {{ ref('stg_suppliers') }}

),

final as (

    select
        supplier_id,
        tenant_id,
        supplier_code,
        supplier_name,
        average_lead_time_days,
        minimum_order_value,
        active,
        created_at

    from suppliers

)

select *
from final