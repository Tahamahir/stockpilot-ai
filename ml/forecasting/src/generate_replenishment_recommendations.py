from __future__ import annotations

import math
import uuid

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.database import get_engine


# =========================================================
# Model validation information
# =========================================================

BACKTEST_RMSE = 5.2987

# Approximation of 95% service level
SERVICE_LEVEL_Z = 1.645


def load_latest_forecast() -> pd.DataFrame:

    query = text(
        """
        with latest_run as (
            select forecast_run_id
            from ml.forecast_runs
            where status = 'completed'
            order by generated_at desc
            limit 1
        )

        select
            forecasts.forecast_run_id,
            forecasts.forecast_date,
            forecasts.horizon_day,

            forecasts.tenant_id,
            forecasts.store_id,
            forecasts.product_id,

            forecasts.predicted_quantity,

            inventory.stock_on_hand,
            inventory.quantity_on_order,
            inventory.backorders,
            inventory.inventory_position,

            inventory.lead_time_days,
            inventory.minimum_order_quantity,
            inventory.package_size

        from ml.demand_forecasts forecasts

        inner join latest_run
            on forecasts.forecast_run_id =
               latest_run.forecast_run_id

        inner join analytics.mart_inventory_health inventory
            on forecasts.tenant_id =
               inventory.tenant_id
            and forecasts.store_id =
                inventory.store_id
            and forecasts.product_id =
                inventory.product_id

        order by
            forecasts.store_id,
            forecasts.product_id,
            forecasts.forecast_date
        """
    )

    engine = get_engine()

    with engine.connect() as connection:
        return pd.read_sql(
            query,
            connection,
        )


def round_to_package(
    requirement: float,
    minimum_order_quantity: float,
    package_size: float,
) -> float:

    if requirement <= 0:
        return 0.0

    minimum_order_quantity = max(
        float(minimum_order_quantity or 0),
        0,
    )

    package_size = max(
        float(package_size or 1),
        1,
    )

    quantity = max(
        requirement,
        minimum_order_quantity,
    )

    return float(
        math.ceil(
            quantity / package_size
        )
        * package_size
    )


def estimate_stockout_date(
    group: pd.DataFrame,
    inventory_position: float,
):

    if inventory_position <= 0:
        return group[
            "forecast_date"
        ].min()

    cumulative_demand = (
        group[
            "predicted_quantity"
        ].cumsum()
    )

    stockout = group[
        cumulative_demand
        >= inventory_position
    ]

    if stockout.empty:
        return None

    return stockout.iloc[0][
        "forecast_date"
    ]


def calculate_urgency(
    stockout_date,
    forecast_start_date,
    recommended_quantity: float,
) -> str:

    if recommended_quantity <= 0:
        return "no_order"

    if stockout_date is None:
        return "planned"

    days_to_stockout = (
        pd.Timestamp(stockout_date)
        - pd.Timestamp(forecast_start_date)
    ).days

    if days_to_stockout <= 3:
        return "critical"

    if days_to_stockout <= 7:
        return "high"

    if days_to_stockout <= 14:
        return "medium"

    return "planned"


def generate_recommendations() -> None:

    forecasts = load_latest_forecast()

    if forecasts.empty:
        raise RuntimeError(
            "No completed forecast run found."
        )

    forecasts[
        "forecast_date"
    ] = pd.to_datetime(
        forecasts["forecast_date"]
    )

    forecast_run_id = str(
        forecasts.iloc[0][
            "forecast_run_id"
        ]
    )

    recommendations = []

    group_columns = [
        "tenant_id",
        "store_id",
        "product_id",
    ]

    for key, group in forecasts.groupby(
        group_columns
    ):

        group = group.sort_values(
            "forecast_date"
        )

        first = group.iloc[0]

        lead_time_days = max(
            int(
                first["lead_time_days"]
                or 1
            ),
            1,
        )

        forecast_30d = float(
            group[
                "predicted_quantity"
            ].sum()
        )

        # Demand expected before supplier arrival
        forecast_lead_time = float(
            group[
                group["horizon_day"]
                <= lead_time_days
            ][
                "predicted_quantity"
            ].sum()
        )

        # ---------------------------------------------
        # Safety stock
        #
        # sigma ≈ backtest RMSE
        #
        # SS = z × sigma × sqrt(lead time)
        # ---------------------------------------------

        safety_stock = float(
            SERVICE_LEVEL_Z
            * BACKTEST_RMSE
            * np.sqrt(
                lead_time_days
            )
        )

        stock_on_hand = float(
            first[
                "stock_on_hand"
            ]
            or 0
        )

        quantity_on_order = float(
            first[
                "quantity_on_order"
            ]
            or 0
        )

        backorders = float(
            first[
                "backorders"
            ]
            or 0
        )

        inventory_position = float(
            first[
                "inventory_position"
            ]
            or 0
        )

        target_stock = (
            forecast_lead_time
            + safety_stock
        )

        net_requirement = max(
            target_stock
            - inventory_position,
            0,
        )

        minimum_order_quantity = float(
            first[
                "minimum_order_quantity"
            ]
            or 0
        )

        package_size = float(
            first[
                "package_size"
            ]
            or 1
        )

        recommended_quantity = (
            round_to_package(
                requirement=net_requirement,
                minimum_order_quantity=(
                    minimum_order_quantity
                ),
                package_size=(
                    package_size
                ),
            )
        )

        stockout_date = (
            estimate_stockout_date(
                group=group,
                inventory_position=(
                    inventory_position
                ),
            )
        )

        forecast_start_date = (
            group[
                "forecast_date"
            ].min()
        )

        urgency = calculate_urgency(
            stockout_date=stockout_date,
            forecast_start_date=(
                forecast_start_date
            ),
            recommended_quantity=(
                recommended_quantity
            ),
        )

        recommendations.append(
            {
                "recommendation_id":
                    str(uuid.uuid4()),

                "forecast_run_id":
                    forecast_run_id,

                "tenant_id":
                    str(key[0]),

                "store_id":
                    str(key[1]),

                "product_id":
                    str(key[2]),

                "forecast_30d":
                    forecast_30d,

                "forecast_lead_time":
                    forecast_lead_time,

                "lead_time_days":
                    lead_time_days,

                "safety_stock_units":
                    safety_stock,

                "stock_on_hand":
                    stock_on_hand,

                "quantity_on_order":
                    quantity_on_order,

                "backorders":
                    backorders,

                "inventory_position":
                    inventory_position,

                "target_stock_units":
                    target_stock,

                "net_requirement_units":
                    net_requirement,

                "minimum_order_quantity":
                    minimum_order_quantity,

                "package_size":
                    package_size,

                "recommended_order_quantity":
                    recommended_quantity,

                "estimated_stockout_date":
                    (
                        stockout_date.date()
                        if stockout_date
                        is not None
                        else None
                    ),

                "urgency_level":
                    urgency,
            }
        )

    recommendation_df = pd.DataFrame(
        recommendations
    )

    engine = get_engine()


    # =========================================================
    # Prepare PostgreSQL records
    # =========================================================

    records = []

    for row in recommendation_df.itertuples(
        index=False
    ):

        records.append(
            {
                "recommendation_id":
                    str(row.recommendation_id),

                "forecast_run_id":
                    str(row.forecast_run_id),

                "tenant_id":
                    str(row.tenant_id),

                "store_id":
                    str(row.store_id),

                "product_id":
                    str(row.product_id),

                "forecast_30d":
                    float(row.forecast_30d),

                "forecast_lead_time":
                    float(row.forecast_lead_time),

                "lead_time_days":
                    int(row.lead_time_days),

                "safety_stock_units":
                    float(row.safety_stock_units),

                "stock_on_hand":
                    float(row.stock_on_hand),

                "quantity_on_order":
                    float(row.quantity_on_order),

                "backorders":
                    float(row.backorders),

                "inventory_position":
                    float(row.inventory_position),

                "target_stock_units":
                    float(row.target_stock_units),

                "net_requirement_units":
                    float(row.net_requirement_units),

                "minimum_order_quantity":
                    float(row.minimum_order_quantity),

                "package_size":
                    float(row.package_size),

                "recommended_order_quantity":
                    float(
                        row.recommended_order_quantity
                    ),

                "estimated_stockout_date":
                    row.estimated_stockout_date,

                "urgency_level":
                    str(row.urgency_level),
            }
        )


    insert_query = text(
        """
        INSERT INTO ml.replenishment_recommendations (
            recommendation_id,
            forecast_run_id,
            tenant_id,
            store_id,
            product_id,

            forecast_30d,
            forecast_lead_time,
            lead_time_days,
            safety_stock_units,

            stock_on_hand,
            quantity_on_order,
            backorders,
            inventory_position,

            target_stock_units,
            net_requirement_units,

            minimum_order_quantity,
            package_size,

            recommended_order_quantity,

            estimated_stockout_date,
            urgency_level
        )
        VALUES (
            CAST(:recommendation_id AS UUID),
            CAST(:forecast_run_id AS UUID),
            CAST(:tenant_id AS UUID),
            CAST(:store_id AS UUID),
            CAST(:product_id AS UUID),

            :forecast_30d,
            :forecast_lead_time,
            :lead_time_days,
            :safety_stock_units,

            :stock_on_hand,
            :quantity_on_order,
            :backorders,
            :inventory_position,

            :target_stock_units,
            :net_requirement_units,

            :minimum_order_quantity,
            :package_size,

            :recommended_order_quantity,

            :estimated_stockout_date,
            :urgency_level
        )
        """
    )


# =========================================================
# Atomic replace for this forecast run
# =========================================================

    with engine.begin() as connection:

        connection.execute(
            text(
                """
                DELETE
                FROM ml.replenishment_recommendations
                WHERE forecast_run_id =
                    CAST(:forecast_run_id AS UUID)
                """
            ),
            {
                "forecast_run_id":
                    forecast_run_id
            },
        )

        connection.execute(
            insert_query,
            records,
        )

    print()
    print("=" * 70)
    print("REPLENISHMENT OPTIMIZATION COMPLETED")
    print("=" * 70)

    print(
        f"Forecast run: "
        f"{forecast_run_id}"
    )

    print(
        f"Product-store combinations: "
        f"{len(recommendation_df):,}"
    )

    print(
        "Products requiring an order: "
        f"{(
            recommendation_df[
                'recommended_order_quantity'
            ] > 0
        ).sum():,}"
    )

    print(
        "Total recommended quantity: "
        f"{recommendation_df[
            'recommended_order_quantity'
        ].sum():,.0f}"
    )

    print()

    print("Urgency breakdown:")

    print(
        recommendation_df[
            "urgency_level"
        ]
        .value_counts()
        .to_string()
    )


if __name__ == "__main__":
    generate_recommendations()