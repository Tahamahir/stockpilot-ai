with sales as (

    select *
    from {{ ref('stg_sales') }}

),

promotions as (

    select *
    from {{ ref('stg_promotions') }}

),

promotion_matches as (

    select
        sales.sale_id,
        sales.tenant_id,
        sales.sale_reference,
        sales.sale_date,
        sales.store_id,
        sales.product_id,
        sales.quantity,
        sales.unit_price,
        sales.discount_percentage as sale_discount_percentage,
        sales.total_amount,
        sales.expected_total_amount,
        sales.total_amount_difference,
        sales.imported_at,

        promotions.promotion_id,
        promotions.start_date as promotion_start_date,
        promotions.end_date as promotion_end_date,
        promotions.discount_percentage
            as promotion_discount_percentage,

        row_number() over (
            partition by sales.sale_id
            order by
                promotions.start_date desc nulls last,
                promotions.promotion_id
        ) as promotion_rank

    from sales

    left join promotions
        on sales.tenant_id = promotions.tenant_id
        and sales.store_id = promotions.store_id
        and sales.product_id = promotions.product_id
        and sales.sale_date between
            promotions.start_date
            and promotions.end_date

),

final as (

    select
        sale_id,
        tenant_id,
        sale_reference,
        sale_date,
        store_id,
        product_id,
        quantity,
        unit_price,
        sale_discount_percentage,
        total_amount,
        expected_total_amount,
        total_amount_difference,

        promotion_id,
        promotion_start_date,
        promotion_end_date,
        promotion_discount_percentage,

        promotion_id is not null
            as is_promotion_sale,

        case
            when promotion_id is not null
                then total_amount
            else 0
        end as promotion_revenue,

        case
            when promotion_id is null
                then total_amount
            else 0
        end as regular_revenue,

        case
            when promotion_id is not null
                and sale_discount_percentage
                    = promotion_discount_percentage
                then true
            when promotion_id is null
                then null
            else false
        end as promotion_discount_matches_sale,

        imported_at

    from promotion_matches

    where promotion_rank = 1

)

select *
from final