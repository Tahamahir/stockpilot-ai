with supplier_performance as (

    select *
    from {{ ref('int_supplier_performance') }}

),

calculated_scores as (

    select
        md5(
            concat_ws(
                '|',
                tenant_id::text,
                supplier_id::text
            )
        ) as supplier_performance_key,

        tenant_id,
        supplier_id,
        supplier_code,
        supplier_name,

        total_purchase_orders,
        delivered_orders,
        open_orders,
        cancelled_orders,
        on_time_deliveries,
        late_deliveries,

        total_ordered_quantity,
        total_received_quantity,

        quantity_fulfillment_rate_percentage,
        average_expected_lead_time_days,
        average_actual_lead_time_days,
        average_delivery_delay_days,
        on_time_delivery_rate_percentage,

        round(
            (
                0.60
                * coalesce(
                    on_time_delivery_rate_percentage,
                    0
                )
            )
            +
            (
                0.40
                * coalesce(
                    quantity_fulfillment_rate_percentage,
                    0
                )
            ),
            2
        ) as supplier_score

    from supplier_performance

),

final as (

    select
        *,

        case
            when supplier_score >= 90
                then 'excellent'

            when supplier_score >= 75
                then 'good'

            when supplier_score >= 60
                then 'needs_monitoring'

            else 'critical'
        end as supplier_performance_tier,

        dense_rank() over (
            partition by tenant_id
            order by supplier_score desc
        ) as supplier_rank

    from calculated_scores

)

select *
from final