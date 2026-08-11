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
# Latest ML replenishment priorities
# =========================================================

def get_replenishment_priorities(
    limit: int = 10,
    urgency: str | None = None,
) -> dict:
    """
    Return the latest ML replenishment recommendations.

    urgency can be:
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
    # Safe dynamic filter
    #
    # The SQL fragment is generated only by our backend.
    # No user-provided SQL is executed.
    # =====================================================

    urgency_filter = ""

    parameters = {
        "limit": limit,
    }

    if urgency is not None:
        urgency_filter = """
            AND recommendations.urgency_level = :urgency
        """

        parameters[
            "urgency"
        ] = urgency

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

            recommendations
                .recommended_order_quantity
                DESC

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
        "recommendations":
            rows_to_dicts(
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

    If store_name is provided, a case-insensitive
    partial store-name match is used.

    Example:
        "Rabat" matches "Magasin Rabat".
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
    # Safe optional store filter
    #
    # We do NOT use:
    # :store_name IS NULL
    #
    # because PostgreSQL may not infer the parameter type.
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
    # Group forecast by store
    #
    # Important when no store was specified:
    # one SKU may exist in several stores.
    # =====================================================

    stores = {}

    for row in results:
        current_store = row[
            "store_name"
        ]

        if current_store not in stores:
            stores[
                current_store
            ] = {
                "store_name":
                    current_store,

                "forecast_total":
                    0.0,

                "daily_forecast":
                    [],
            }

        predicted_quantity = float(
            row[
                "predicted_quantity"
            ]
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
                    row[
                        "forecast_date"
                    ],

                "horizon_day":
                    row[
                        "horizon_day"
                    ],

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
            first_row[
                "sku"
            ],

        "product_name":
            first_row[
                "product_name"
            ],

        "category_name":
            first_row[
                "category_name"
            ],

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
            len(
                store_results
            ),

        "forecast_total":
            total_forecast,

        "stores":
            store_results,
    }