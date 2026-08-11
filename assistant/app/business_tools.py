from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.database import get_engine


# =========================================================
# Helpers
# =========================================================

def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    return value


def rows_to_dicts(rows) -> list[dict]:
    return [
        {
            key: json_safe(value)
            for key, value in row.items()
        }
        for row in rows
    ]


# =========================================================
# TOOL 1
# Inventory overview
# =========================================================

def get_inventory_summary() -> dict:
    """
    Return the current inventory health summary.
    """

    query = text(
        """
        SELECT
            COUNT(*) AS product_store_count,

            COUNT(*) FILTER (
                WHERE inventory_health_status = 'critical'
            ) AS critical_count,

            COUNT(*) FILTER (
                WHERE inventory_health_status = 'out_of_stock'
            ) AS out_of_stock_count,

            COUNT(*) FILTER (
                WHERE inventory_health_status = 'low_stock'
            ) AS low_stock_count,

            COUNT(*) FILTER (
                WHERE inventory_health_status = 'overstock'
            ) AS overstock_count,

            COUNT(*) FILTER (
                WHERE inventory_health_status = 'healthy'
            ) AS healthy_count,

            ROUND(
                SUM(stock_value_at_cost)::numeric,
                2
            ) AS stock_value_at_cost,

            ROUND(
                SUM(recommended_order_quantity)::numeric,
                0
            ) AS historical_recommended_order_quantity

        FROM analytics.mart_inventory_health
        """
    )

    engine = get_engine()

    with engine.connect() as connection:
        result = (
            connection
            .execute(query)
            .mappings()
            .one()
        )

    return {
        "scope": "product_store_combinations",
        "currency": "MAD",
        **{
            key: json_safe(value)
            for key, value in result.items()
        },
    }


# =========================================================
# TOOL 2
# ML replenishment priorities
# =========================================================

def get_replenishment_priorities(
    limit: int = 10,
    urgency: str | None = None,
) -> dict:
    """
    Return latest ML replenishment recommendations.

    urgency:
    critical, high, medium, planned, no_order
    """

    limit = max(
        1,
        min(
            int(limit),
            50,
        ),
    )

    allowed_urgencies = {
        "critical",
        "high",
        "medium",
        "planned",
        "no_order",
    }

    if urgency:
        urgency = (
            urgency
            .strip()
            .lower()
        )

        if urgency not in allowed_urgencies:
            return {
                "error": (
                    "Invalid urgency. "
                    "Allowed values: "
                    + ", ".join(
                        sorted(
                            allowed_urgencies
                        )
                    )
                )
            }

    else:
        urgency = None

    # =====================================================
    # Optional filter
    #
    # We intentionally do NOT use:
    # :urgency IS NULL
    #
    # because PostgreSQL may fail to infer the parameter
    # type through psycopg.
    # =====================================================

    urgency_filter = ""

    parameters = {
        "limit": limit,
    }

    if urgency is not None:
        urgency_filter = """
            AND recommendations.urgency_level = :urgency
        """

        parameters["urgency"] = urgency

    query = text(
        f"""
        WITH latest_run AS (
            SELECT
                forecast_run_id

            FROM ml.forecast_runs

            WHERE status = 'completed'

            ORDER BY generated_at DESC

            LIMIT 1
        )

        SELECT
            products.sku,
            products.product_name,
            products.category_name,

            stores.store_name,

            recommendations.forecast_30d,
            recommendations.forecast_lead_time,
            recommendations.lead_time_days,

            recommendations.stock_on_hand,
            recommendations.quantity_on_order,
            recommendations.backorders,
            recommendations.inventory_position,

            recommendations.safety_stock_units,

            recommendations.minimum_order_quantity,
            recommendations.package_size,

            recommendations.recommended_order_quantity,

            recommendations.estimated_stockout_date,
            recommendations.urgency_level

        FROM ml.replenishment_recommendations
            AS recommendations

        INNER JOIN latest_run
            ON recommendations.forecast_run_id =
               latest_run.forecast_run_id

        LEFT JOIN analytics.dim_products
            AS products
            ON recommendations.tenant_id =
               products.tenant_id
            AND recommendations.product_id =
                products.product_id

        LEFT JOIN analytics.dim_stores
            AS stores
            ON recommendations.tenant_id =
               stores.tenant_id
            AND recommendations.store_id =
                stores.store_id

        WHERE
            recommendations.recommended_order_quantity > 0

            {urgency_filter}

        ORDER BY
            CASE
                recommendations.urgency_level

                WHEN 'critical'
                    THEN 1

                WHEN 'high'
                    THEN 2

                WHEN 'medium'
                    THEN 3

                WHEN 'planned'
                    THEN 4

                ELSE 5
            END,

            recommendations.recommended_order_quantity DESC

        LIMIT :limit
        """
    )

    engine = get_engine()

    with engine.connect() as connection:
        rows = (
            connection
            .execute(
                query,
                parameters,
            )
            .mappings()
            .all()
        )

    return {
        "count": len(rows),
        "urgency_filter": urgency,
        "recommendations": rows_to_dicts(
            rows
        ),
    }


# =========================================================
# TOOL 3
# Product forecast
# =========================================================

def get_product_forecast(
    sku: str,
    store_name: str | None = None,
) -> dict:
    """
    Return the latest demand forecast for one SKU.

    A partial case-insensitive store match is allowed.

    Example:
        Rabat -> Magasin Rabat
    """

    sku = (
        sku
        .strip()
        .upper()
    )

    if not sku:
        return {
            "found": False,
            "error": "SKU cannot be empty.",
        }

    if store_name:
        store_name = (
            store_name
            .strip()
        )
    else:
        store_name = None

    # =====================================================
    # Optional store filter
    # =====================================================

    store_filter = ""

    parameters = {
        "sku": sku,
    }

    if store_name:
        store_filter = """
            AND LOWER(stores.store_name)
                LIKE LOWER(:store_pattern)
        """

        parameters[
            "store_pattern"
        ] = f"%{store_name}%"

    query = text(
        f"""
        WITH latest_run AS (
            SELECT
                forecast_run_id,
                forecast_start_date,
                forecast_end_date,
                horizon_days,
                generated_at

            FROM ml.forecast_runs

            WHERE status = 'completed'

            ORDER BY generated_at DESC

            LIMIT 1
        )

        SELECT
            products.sku,
            products.product_name,
            products.category_name,

            stores.store_name,

            forecasts.forecast_date,
            forecasts.horizon_day,

            ROUND(
                forecasts.predicted_quantity::numeric,
                2
            ) AS predicted_quantity,

            latest_run.forecast_start_date,
            latest_run.forecast_end_date,
            latest_run.horizon_days

        FROM ml.demand_forecasts
            AS forecasts

        INNER JOIN latest_run
            ON forecasts.forecast_run_id =
               latest_run.forecast_run_id

        INNER JOIN analytics.dim_products
            AS products
            ON forecasts.tenant_id =
               products.tenant_id
            AND forecasts.product_id =
                products.product_id

        INNER JOIN analytics.dim_stores
            AS stores
            ON forecasts.tenant_id =
               stores.tenant_id
            AND forecasts.store_id =
                stores.store_id

        WHERE
            UPPER(products.sku) =
            UPPER(:sku)

            {store_filter}

        ORDER BY
            stores.store_name,
            forecasts.forecast_date
        """
    )

    engine = get_engine()

    with engine.connect() as connection:
        rows = (
            connection
            .execute(
                query,
                parameters,
            )
            .mappings()
            .all()
        )

    results = rows_to_dicts(
        rows
    )

    if not results:
        return {
            "found": False,
            "sku": sku,
            "store_search": store_name,
            "message": (
                "No forecast found for "
                "the requested SKU/store."
            ),
        }

    # =====================================================
    # Group by store
    # =====================================================

    stores: dict[str, dict] = {}

    for row in results:
        current_store = row[
            "store_name"
        ]

        if current_store not in stores:
            stores[current_store] = {
                "store_name": current_store,
                "forecast_total": 0.0,
                "daily_forecast": [],
            }

        predicted_quantity = float(
            row["predicted_quantity"]
        )

        stores[
            current_store
        ][
            "forecast_total"
        ] += predicted_quantity

        stores[
            current_store
        ][
            "daily_forecast"
        ].append(
            {
                "forecast_date":
                    row["forecast_date"],

                "horizon_day":
                    row["horizon_day"],

                "predicted_quantity":
                    predicted_quantity,
            }
        )

    store_results = []

    for store_data in stores.values():
        store_data[
            "forecast_total"
        ] = round(
            store_data[
                "forecast_total"
            ],
            2,
        )

        store_results.append(
            store_data
        )

    total_forecast = round(
        sum(
            store[
                "forecast_total"
            ]
            for store in store_results
        ),
        2,
    )

    first_row = results[0]

    return {
        "found": True,

        "sku":
            first_row["sku"],

        "product_name":
            first_row["product_name"],

        "category_name":
            first_row["category_name"],

        "store_search":
            store_name,

        "forecast_start_date":
            first_row[
                "forecast_start_date"
            ],

        "forecast_end_date":
            first_row[
                "forecast_end_date"
            ],

        "horizon_days":
            first_row[
                "horizon_days"
            ],

        "number_of_stores":
            len(store_results),

        "forecast_total":
            total_forecast,

        "stores":
            store_results,
    }


# =========================================================
# TOOL 4
# Sales performance
# =========================================================

def get_sales_performance(
    limit: int = 10,
) -> dict:
    """
    Return:
    - global sales KPIs
    - top products by quantity
    - top products by revenue
    - store performance
    """

    limit = max(
        1,
        min(
            int(limit),
            50,
        ),
    )

    # =====================================================
    # Global KPIs
    # =====================================================

    summary_query = text(
        """
        SELECT
            MIN(sale_date)
                AS start_date,

            MAX(sale_date)
                AS end_date,

            SUM(transaction_count)
                AS transaction_count,

            SUM(total_quantity_sold)
                AS total_quantity_sold,

            ROUND(
                SUM(net_revenue)::numeric,
                2
            ) AS net_revenue,

            ROUND(
                SUM(total_discount_amount)::numeric,
                2
            ) AS total_discount_amount,

            ROUND(
                SUM(gross_margin)::numeric,
                2
            ) AS gross_margin,

            ROUND(
                (
                    100.0
                    * SUM(gross_margin)
                    / NULLIF(
                        SUM(net_revenue),
                        0
                    )
                )::numeric,
                2
            ) AS gross_margin_rate_percentage,

            ROUND(
                (
                    SUM(net_revenue)
                    / NULLIF(
                        SUM(transaction_count),
                        0
                    )
                )::numeric,
                2
            ) AS average_basket_value,

            COUNT(
                DISTINCT product_id
            ) AS unique_products,

            COUNT(
                DISTINCT store_id
            ) AS unique_stores

        FROM analytics.fct_daily_sales
        """
    )

    # =====================================================
    # Top products by quantity
    # =====================================================

    top_quantity_query = text(
        """
        SELECT
            sku,
            product_name,
            category_name,

            SUM(total_quantity_sold)
                AS quantity_sold,

            ROUND(
                SUM(net_revenue)::numeric,
                2
            ) AS net_revenue,

            ROUND(
                SUM(gross_margin)::numeric,
                2
            ) AS gross_margin

        FROM analytics.fct_daily_sales

        GROUP BY
            sku,
            product_name,
            category_name

        ORDER BY
            quantity_sold DESC,
            net_revenue DESC

        LIMIT :limit
        """
    )

    # =====================================================
    # Top products by revenue
    # =====================================================

    top_revenue_query = text(
        """
        SELECT
            sku,
            product_name,
            category_name,

            SUM(total_quantity_sold)
                AS quantity_sold,

            ROUND(
                SUM(net_revenue)::numeric,
                2
            ) AS net_revenue,

            ROUND(
                SUM(gross_margin)::numeric,
                2
            ) AS gross_margin

        FROM analytics.fct_daily_sales

        GROUP BY
            sku,
            product_name,
            category_name

        ORDER BY
            net_revenue DESC,
            quantity_sold DESC

        LIMIT :limit
        """
    )

    # =====================================================
    # Store performance
    # =====================================================

    stores_query = text(
        """
        SELECT
            stores.store_name,
            stores.city,
            stores.region,

            SUM(
                sales.transaction_count
            ) AS transaction_count,

            SUM(
                sales.total_quantity_sold
            ) AS quantity_sold,

            ROUND(
                SUM(
                    sales.net_revenue
                )::numeric,
                2
            ) AS net_revenue,

            ROUND(
                SUM(
                    sales.gross_margin
                )::numeric,
                2
            ) AS gross_margin,

            ROUND(
                (
                    100.0
                    * SUM(
                        sales.gross_margin
                    )
                    / NULLIF(
                        SUM(
                            sales.net_revenue
                        ),
                        0
                    )
                )::numeric,
                2
            ) AS gross_margin_rate_percentage

        FROM analytics.fct_daily_sales
            AS sales

        INNER JOIN analytics.dim_stores
            AS stores
            ON sales.tenant_id =
               stores.tenant_id
            AND sales.store_id =
                stores.store_id

        GROUP BY
            stores.store_id,
            stores.store_name,
            stores.city,
            stores.region

        ORDER BY
            net_revenue DESC

        LIMIT :limit
        """
    )

    engine = get_engine()

    with engine.connect() as connection:
        summary = (
            connection
            .execute(
                summary_query
            )
            .mappings()
            .one()
        )

        top_by_quantity = (
            connection
            .execute(
                top_quantity_query,
                {
                    "limit": limit,
                },
            )
            .mappings()
            .all()
        )

        top_by_revenue = (
            connection
            .execute(
                top_revenue_query,
                {
                    "limit": limit,
                },
            )
            .mappings()
            .all()
        )

        stores = (
            connection
            .execute(
                stores_query,
                {
                    "limit": limit,
                },
            )
            .mappings()
            .all()
        )

    return {
        "currency": "MAD",

        "summary": {
            key: json_safe(value)
            for key, value
            in summary.items()
        },

        "top_products_by_quantity":
            rows_to_dicts(
                top_by_quantity
            ),

        "top_products_by_revenue":
            rows_to_dicts(
                top_by_revenue
            ),

        "stores":
            rows_to_dicts(
                stores
            ),
    }
# =========================================================
# TOOL 5
# Supplier performance
# =========================================================

def get_supplier_performance(
    limit: int = 10,
) -> dict:
    """
    Return:
    - best suppliers
    - suppliers with the most delivery problems
    - global supplier KPIs
    """

    limit = max(
        1,
        min(int(limit), 50),
    )

    # =====================================================
    # Global supplier KPIs
    # =====================================================

    summary_query = text(
        """
        SELECT
            COUNT(*) AS supplier_count,

            ROUND(
                AVG(supplier_score)::numeric,
                2
            ) AS average_supplier_score,

            ROUND(
                AVG(
                    on_time_delivery_rate_percentage
                )::numeric,
                2
            ) AS average_on_time_delivery_rate_percentage,

            ROUND(
                AVG(
                    quantity_fulfillment_rate_percentage
                )::numeric,
                2
            ) AS average_fulfillment_rate_percentage,

            SUM(total_purchase_orders)
                AS total_purchase_orders,

            SUM(late_deliveries)
                AS total_late_deliveries,

            ROUND(
                AVG(
                    average_delivery_delay_days
                )::numeric,
                2
            ) AS average_delivery_delay_days

        FROM analytics.mart_supplier_performance
        """
    )

    # =====================================================
    # Best suppliers
    # =====================================================

    best_query = text(
        """
        SELECT
            supplier_code,
            supplier_name,

            total_purchase_orders,
            delivered_orders,
            open_orders,
            cancelled_orders,

            on_time_deliveries,
            late_deliveries,

            quantity_fulfillment_rate_percentage,
            on_time_delivery_rate_percentage,

            average_expected_lead_time_days,
            average_actual_lead_time_days,
            average_delivery_delay_days,

            supplier_score,
            supplier_performance_tier,
            supplier_rank

        FROM analytics.mart_supplier_performance

        ORDER BY
            supplier_score DESC,
            supplier_rank ASC

        LIMIT :limit
        """
    )

    # =====================================================
    # Suppliers with delivery problems
    #
    # Priority:
    # 1. lowest on-time delivery rate
    # 2. most late deliveries
    # 3. highest average delay
    # =====================================================

    risk_query = text(
        """
        SELECT
            supplier_code,
            supplier_name,

            total_purchase_orders,
            delivered_orders,
            open_orders,
            cancelled_orders,

            on_time_deliveries,
            late_deliveries,

            quantity_fulfillment_rate_percentage,
            on_time_delivery_rate_percentage,

            average_expected_lead_time_days,
            average_actual_lead_time_days,
            average_delivery_delay_days,

            supplier_score,
            supplier_performance_tier,
            supplier_rank

        FROM analytics.mart_supplier_performance

        ORDER BY
            on_time_delivery_rate_percentage ASC,
            late_deliveries DESC,
            average_delivery_delay_days DESC

        LIMIT :limit
        """
    )

    engine = get_engine()

    with engine.connect() as connection:
        summary = (
            connection
            .execute(summary_query)
            .mappings()
            .one()
        )

        best_suppliers = (
            connection
            .execute(
                best_query,
                {"limit": limit},
            )
            .mappings()
            .all()
        )

        suppliers_at_risk = (
            connection
            .execute(
                risk_query,
                {"limit": limit},
            )
            .mappings()
            .all()
        )

    best_suppliers = rows_to_dicts(
        best_suppliers
    )

    suppliers_at_risk = rows_to_dicts(
        suppliers_at_risk
    )

    return {
        "summary": {
            key: json_safe(value)
            for key, value
            in summary.items()
        },

        "best_supplier": (
            best_suppliers[0]
            if best_suppliers
            else None
        ),

        "best_suppliers":
            best_suppliers,

        "suppliers_at_risk":
            suppliers_at_risk,
    }