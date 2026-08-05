with products as (

    select *
    from {{ ref('stg_products') }}

),

final as (

    select
        product_id,
        tenant_id,
        supplier_id,
        sku,
        product_name,
        category_name,
        purchase_price,
        selling_price,

        round(
            selling_price - purchase_price,
            2
        ) as unit_margin,

        round(
            100.0
            * (selling_price - purchase_price)
            / nullif(selling_price, 0),
            2
        ) as margin_rate_percentage,

        lead_time_days,
        minimum_order_quantity,
        package_size,
        active,
        created_at

    from products

)

select *
from final