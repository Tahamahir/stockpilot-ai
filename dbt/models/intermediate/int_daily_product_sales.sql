with sales as (

    select *
    from {{ ref('stg_sales') }}

),

daily_sales as (

    select
        tenant_id,
        sale_date,
        store_id,
        product_id,

        count(distinct sale_id) as transaction_count,

        sum(quantity) as total_quantity_sold,

        round(
            sum(quantity * unit_price),
            2
        ) as gross_revenue,

        round(
            sum(
                quantity
                * unit_price
                * discount_percentage
                / 100
            ),
            2
        ) as total_discount_amount,

        round(
            sum(total_amount),
            2
        ) as net_revenue,

        round(
            avg(unit_price),
            2
        ) as average_unit_price,

        round(
            avg(discount_percentage),
            2
        ) as average_discount_percentage

    from sales

    group by
        tenant_id,
        sale_date,
        store_id,
        product_id

)

select *
from daily_sales