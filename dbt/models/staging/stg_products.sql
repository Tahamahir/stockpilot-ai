with source_data as (

    select *
    from {{ source('stockpilot_raw', 'products') }}

),

cleaned as (

    select
        product_id,
        tenant_id,
        supplier_id,
        upper(trim(sku)) as sku,
        trim(product_name) as product_name,
        nullif(trim(category_name), '') as category_name,
        purchase_price,
        selling_price,
        lead_time_days,
        minimum_order_quantity,
        package_size,
        active,
        created_at

    from source_data

)

select *
from cleaned