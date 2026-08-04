with purchase_orders as (

    select *
    from {{ ref('stg_purchase_orders') }}

),

suppliers as (

    select *
    from {{ ref('stg_suppliers') }}

),

supplier_performance as (

    select
        purchase_orders.tenant_id,
        purchase_orders.supplier_id,
        suppliers.supplier_code,
        suppliers.supplier_name,

        count(*) as total_purchase_orders,

        count(*) filter (
            where purchase_orders.actual_delivery_date is not null
        ) as delivered_orders,

        count(*) filter (
            where purchase_orders.actual_delivery_date is null
            and purchase_orders.status <> 'cancelled'
        ) as open_orders,

        count(*) filter (
            where purchase_orders.status = 'cancelled'
        ) as cancelled_orders,

        count(*) filter (
            where purchase_orders.actual_delivery_date is not null
            and purchase_orders.delivery_delay_days <= 0
        ) as on_time_deliveries,

        count(*) filter (
            where purchase_orders.actual_delivery_date is not null
            and purchase_orders.delivery_delay_days > 0
        ) as late_deliveries,

        sum(
            purchase_orders.ordered_quantity
        ) as total_ordered_quantity,

        sum(
            purchase_orders.received_quantity
        ) as total_received_quantity,

        round(
            100.0
            * sum(purchase_orders.received_quantity)
            / nullif(
                sum(purchase_orders.ordered_quantity),
                0
            ),
            2
        ) as quantity_fulfillment_rate_percentage,

        round(
            avg(
                purchase_orders.expected_lead_time_days
            ),
            2
        ) as average_expected_lead_time_days,

        round(
            avg(
                purchase_orders.actual_lead_time_days
            ) filter (
                where purchase_orders.actual_lead_time_days
                    is not null
            ),
            2
        ) as average_actual_lead_time_days,

        round(
            avg(
                purchase_orders.delivery_delay_days
            ) filter (
                where purchase_orders.delivery_delay_days
                    is not null
            ),
            2
        ) as average_delivery_delay_days,

        round(
            100.0
            * count(*) filter (
                where purchase_orders.actual_delivery_date
                    is not null
                and purchase_orders.delivery_delay_days <= 0
            )
            / nullif(
                count(*) filter (
                    where purchase_orders.actual_delivery_date
                        is not null
                ),
                0
            ),
            2
        ) as on_time_delivery_rate_percentage

    from purchase_orders

    inner join suppliers
        on purchase_orders.supplier_id
            = suppliers.supplier_id
        and purchase_orders.tenant_id
            = suppliers.tenant_id

    group by
        purchase_orders.tenant_id,
        purchase_orders.supplier_id,
        suppliers.supplier_code,
        suppliers.supplier_name

)

select *
from supplier_performance