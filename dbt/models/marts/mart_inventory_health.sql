with latest_inventory_ranked as (

    select
        inventory.*,

        row_number() over (
            partition by
                inventory.tenant_id,
                inventory.store_id,
                inventory.product_id
            order by
                inventory.inventory_date desc,
                inventory.imported_at desc
        ) as inventory_rank

    from {{ ref('fct_inventory_daily') }} as inventory

),

latest_inventory as (

    select *
    from latest_inventory_ranked
    where inventory_rank = 1

),

sales_reference_date as (

    select max(sale_date) as maximum_sale_date
    from {{ ref('fct_daily_sales') }}

),

recent_sales as (

    select
        sales.tenant_id,
        sales.store_id,
        sales.product_id,

        sum(sales.total_quantity_sold)
            as quantity_sold_last_30_days,

        round(
            sum(sales.net_revenue),
            2
        ) as revenue_last_30_days

    from {{ ref('fct_daily_sales') }} as sales

    cross join sales_reference_date

    where sales.sale_date
        > sales_reference_date.maximum_sale_date - interval '30 days'

    group by
        sales.tenant_id,
        sales.store_id,
        sales.product_id

),

inventory_metrics as (

    select
        md5(
            concat_ws(
                '|',
                inventory.tenant_id::text,
                inventory.store_id::text,
                inventory.product_id::text
            )
        ) as inventory_health_key,

        inventory.tenant_id,
        inventory.inventory_date as snapshot_date,
        inventory.store_id,
        inventory.product_id,
        inventory.supplier_id,
        inventory.sku,
        inventory.product_name,
        inventory.category_name,

        inventory.stock_on_hand,
        inventory.quantity_on_order,
        inventory.backorders,
        inventory.inventory_position,

        inventory.stock_value_at_cost,
        inventory.stock_value_at_retail,
        inventory.inventory_position_value_at_cost,

        inventory.is_out_of_stock,
        inventory.has_backorders,

        products.lead_time_days,
        products.minimum_order_quantity,
        products.package_size,

        coalesce(
            sales.quantity_sold_last_30_days,
            0
        ) as quantity_sold_last_30_days,

        coalesce(
            sales.revenue_last_30_days,
            0
        ) as revenue_last_30_days,

        round(
            coalesce(
                sales.quantity_sold_last_30_days,
                0
            )::numeric / 30,
            2
        ) as average_daily_sales_30d

    from latest_inventory as inventory

    inner join {{ ref('dim_products') }} as products
        on inventory.tenant_id = products.tenant_id
        and inventory.product_id = products.product_id

    left join recent_sales as sales
        on inventory.tenant_id = sales.tenant_id
        and inventory.store_id = sales.store_id
        and inventory.product_id = sales.product_id

),

calculated_metrics as (

    select
        *,

        case
            when average_daily_sales_30d > 0
                then round(
                    stock_on_hand
                    / average_daily_sales_30d,
                    2
                )
            else null
        end as days_of_stock,

        ceiling(
            average_daily_sales_30d
            * lead_time_days
        ) as reorder_point_units,

        greatest(
            0,
            ceiling(
                average_daily_sales_30d
                * (lead_time_days + 30)
                - inventory_position
            )
        ) as raw_recommended_order_quantity

    from inventory_metrics

),

final as (

    select
        inventory_health_key,
        tenant_id,
        snapshot_date,
        store_id,
        product_id,
        supplier_id,
        sku,
        product_name,
        category_name,

        stock_on_hand,
        quantity_on_order,
        backorders,
        inventory_position,

        stock_value_at_cost,
        stock_value_at_retail,
        inventory_position_value_at_cost,

        quantity_sold_last_30_days,
        revenue_last_30_days,
        average_daily_sales_30d,
        days_of_stock,

        lead_time_days,
        minimum_order_quantity,
        package_size,
        reorder_point_units,

        case
            when raw_recommended_order_quantity <= 0
                then 0

            else greatest(
                minimum_order_quantity,
                ceiling(
                    raw_recommended_order_quantity
                    / nullif(package_size, 0)::numeric
                ) * package_size
            )
        end as recommended_order_quantity,

        is_out_of_stock,
        has_backorders,

        case
            when is_out_of_stock
                then 'out_of_stock'

            when has_backorders
                then 'backorder_risk'

            when average_daily_sales_30d = 0
                then 'no_recent_sales'

            when inventory_position <= reorder_point_units
                then 'critical'

            when days_of_stock < 30
                then 'low_stock'

            when days_of_stock > 90
                then 'overstock'

            else 'healthy'
        end as inventory_health_status

    from calculated_metrics

)

select *
from final