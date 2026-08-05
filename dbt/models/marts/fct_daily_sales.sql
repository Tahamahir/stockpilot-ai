with daily_sales as (

    select *
    from {{ ref('int_daily_product_sales') }}

),

products as (

    select *
    from {{ ref('dim_products') }}

),

final as (

    select
        md5(
            concat_ws(
                '|',
                daily_sales.tenant_id::text,
                daily_sales.sale_date::text,
                daily_sales.store_id::text,
                daily_sales.product_id::text
            )
        ) as daily_sales_key,

        daily_sales.tenant_id,
        daily_sales.sale_date,
        daily_sales.store_id,
        daily_sales.product_id,

        products.supplier_id,
        products.sku,
        products.product_name,
        products.category_name,

        daily_sales.transaction_count,
        daily_sales.total_quantity_sold,
        daily_sales.gross_revenue,
        daily_sales.total_discount_amount,
        daily_sales.net_revenue,
        daily_sales.average_unit_price,
        daily_sales.average_discount_percentage,

        products.purchase_price,

        round(
            daily_sales.total_quantity_sold
            * products.purchase_price,
            2
        ) as estimated_cost_of_goods_sold,

        round(
            daily_sales.net_revenue
            - (
                daily_sales.total_quantity_sold
                * products.purchase_price
            ),
            2
        ) as gross_margin,

        round(
            100.0
            * (
                daily_sales.net_revenue
                - (
                    daily_sales.total_quantity_sold
                    * products.purchase_price
                )
            )
            / nullif(daily_sales.net_revenue, 0),
            2
        ) as gross_margin_rate_percentage

    from daily_sales

    inner join products
        on daily_sales.tenant_id = products.tenant_id
        and daily_sales.product_id = products.product_id

)

select *
from final