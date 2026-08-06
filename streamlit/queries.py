from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import text

from database import get_engine


@st.cache_data(ttl=60)
def load_overview_metrics() -> dict[str, float | int]:
    """Load the principal StockPilot dashboard indicators."""

    query = text(
        """
        with sales_metrics as (
            select
                coalesce(sum(net_revenue), 0) as total_revenue,
                coalesce(sum(total_quantity_sold), 0)
                    as total_quantity_sold,
                coalesce(sum(gross_margin), 0) as total_gross_margin
            from analytics.fct_daily_sales
        ),

        inventory_metrics as (
            select
                count(*) filter (
                    where inventory_health_status = 'out_of_stock'
                ) as out_of_stock_count,

                count(*) filter (
                    where inventory_health_status = 'low_stock'
                ) as low_stock_count,

                count(*) filter (
                    where inventory_health_status = 'critical'
                ) as critical_stock_count,

                coalesce(
                    sum(recommended_order_quantity),
                    0
                ) as recommended_order_quantity,

                coalesce(
                    sum(stock_value_at_cost),
                    0
                ) as current_stock_value
            from analytics.mart_inventory_health
        ),

        supplier_metrics as (
            select
                count(*) as supplier_count,
                coalesce(avg(supplier_score), 0)
                    as average_supplier_score
            from analytics.mart_supplier_performance
        )

        select
            sales_metrics.total_revenue,
            sales_metrics.total_quantity_sold,
            sales_metrics.total_gross_margin,

            inventory_metrics.out_of_stock_count,
            inventory_metrics.low_stock_count,
            inventory_metrics.critical_stock_count,
            inventory_metrics.recommended_order_quantity,
            inventory_metrics.current_stock_value,

            supplier_metrics.supplier_count,
            supplier_metrics.average_supplier_score

        from sales_metrics
        cross join inventory_metrics
        cross join supplier_metrics
        """
    )

    engine = get_engine()

    with engine.connect() as connection:
        result = connection.execute(query).mappings().one()

    return dict(result)


@st.cache_data(ttl=60)
def load_inventory_health_summary() -> pd.DataFrame:
    """Load the number of product-store combinations by stock status."""

    query = text(
        """
        select
            inventory_health_status,
            count(*) as product_store_count,
            coalesce(
                sum(recommended_order_quantity),
                0
            ) as recommended_units

        from analytics.mart_inventory_health

        group by inventory_health_status

        order by product_store_count desc
        """
    )

    engine = get_engine()

    with engine.connect() as connection:
        return pd.read_sql(query, connection)

@st.cache_data(ttl=60)
def load_inventory_health_details() -> pd.DataFrame:
    """Load inventory health with readable store information."""

    query = text(
        """
        select
            inventory.inventory_health_key,
            inventory.snapshot_date,
            inventory.tenant_id,
            inventory.store_id,

            stores.store_code,
            stores.store_name,

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

            inventory.quantity_sold_last_30_days,
            inventory.revenue_last_30_days,
            inventory.average_daily_sales_30d,
            inventory.days_of_stock,

            inventory.lead_time_days,
            inventory.minimum_order_quantity,
            inventory.package_size,
            inventory.reorder_point_units,
            inventory.recommended_order_quantity,

            inventory.is_out_of_stock,
            inventory.has_backorders,
            inventory.inventory_health_status

        from analytics.mart_inventory_health as inventory

        left join analytics.dim_stores as stores
            on inventory.store_id = stores.store_id
            and inventory.tenant_id = stores.tenant_id

        order by
            inventory.recommended_order_quantity desc,
            inventory.product_name,
            stores.store_name
        """
    )

    engine = get_engine()

    with engine.connect() as connection:
        return pd.read_sql(query, connection)
    """Load detailed inventory health and replenishment recommendations."""

    query = text(
        """
        select
            inventory_health_key,
            snapshot_date,
            tenant_id,
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
            quantity_sold_last_30_days,
            revenue_last_30_days,
            average_daily_sales_30d,
            days_of_stock,
            lead_time_days,
            minimum_order_quantity,
            package_size,
            reorder_point_units,
            recommended_order_quantity,
            is_out_of_stock,
            has_backorders,
            inventory_health_status

        from analytics.mart_inventory_health

        order by
            recommended_order_quantity desc,
            product_name,
            store_id
        """
    )

    engine = get_engine()

    with engine.connect() as connection:
        return pd.read_sql(query, connection)
@st.cache_data(ttl=60)
def load_sales_analytics_details() -> pd.DataFrame:
    """Load daily sales enriched with store information."""

    query = text(
        """
        select
            sales.daily_sales_key,
            sales.sale_date,
            sales.tenant_id,
            sales.store_id,
            stores.store_code,
            stores.store_name,
            stores.city,
            stores.region,

            sales.product_id,
            sales.supplier_id,
            sales.sku,
            sales.product_name,
            sales.category_name,

            sales.transaction_count,
            sales.total_quantity_sold,
            sales.gross_revenue,
            sales.total_discount_amount,
            sales.net_revenue,
            sales.average_unit_price,
            sales.average_discount_percentage,

            sales.purchase_price,
            sales.estimated_cost_of_goods_sold,
            sales.gross_margin,
            sales.gross_margin_rate_percentage

        from analytics.fct_daily_sales as sales

        left join analytics.dim_stores as stores
            on sales.store_id = stores.store_id
            and sales.tenant_id = stores.tenant_id

        order by
            sales.sale_date,
            stores.store_name,
            sales.product_name
        """
    )

    engine = get_engine()

    with engine.connect() as connection:
        return pd.read_sql(query, connection)
@st.cache_data(ttl=60)
def load_supplier_performance_details() -> pd.DataFrame:
    """Load supplier performance scores and delivery indicators."""

    query = text(
        """
        select
            supplier_performance_key,
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

            supplier_score,
            supplier_performance_tier,
            supplier_rank

        from analytics.mart_supplier_performance

        order by
            supplier_rank,
            supplier_name
        """
    )

    engine = get_engine()

    with engine.connect() as connection:
        return pd.read_sql(query, connection)