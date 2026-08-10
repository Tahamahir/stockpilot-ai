from __future__ import annotations

import pandas as pd

from src.database import load_daily_sales


SERIES_COLUMNS = [
    "tenant_id",
    "store_id",
    "product_id",
]

TARGET_COLUMN = "quantity_sold"


def build_forecasting_dataset() -> pd.DataFrame:
    """
    Build a complete daily forecasting dataset.

    One row represents:
        one date
        + one store
        + one product

    All lag and rolling features use only historical demand.
    """

    sales = load_daily_sales()

    if sales.empty:
        raise RuntimeError(
            "analytics.fct_daily_sales does not contain any data."
        )

    # =====================================================
    # Basic cleaning
    # =====================================================
    sales["sale_date"] = pd.to_datetime(
        sales["sale_date"],
        errors="raise",
    )

    sales[TARGET_COLUMN] = pd.to_numeric(
        sales[TARGET_COLUMN],
        errors="coerce",
    ).fillna(0.0)

    # =====================================================
    # Build complete store-product-date grid
    # =====================================================
    series = sales[
        SERIES_COLUMNS
    ].drop_duplicates()

    dates = pd.DataFrame(
        {
            "sale_date": pd.date_range(
                start=sales["sale_date"].min(),
                end=sales["sale_date"].max(),
                freq="D",
            )
        }
    )

    complete_grid = series.merge(
        dates,
        how="cross",
    )

    dataset = complete_grid.merge(
        sales,
        on=SERIES_COLUMNS + ["sale_date"],
        how="left",
    )

    # A missing transaction day means zero demand.
    dataset[TARGET_COLUMN] = (
        dataset[TARGET_COLUMN]
        .fillna(0.0)
        .astype(float)
    )

    dataset = dataset.sort_values(
        SERIES_COLUMNS + ["sale_date"]
    ).reset_index(drop=True)

    # =====================================================
    # Historical demand features
    # =====================================================
    grouped_sales = dataset.groupby(
        SERIES_COLUMNS,
        sort=False,
    )[TARGET_COLUMN]

    # Lags
    dataset["lag_1"] = grouped_sales.shift(1)
    dataset["lag_7"] = grouped_sales.shift(7)
    dataset["lag_14"] = grouped_sales.shift(14)
    dataset["lag_28"] = grouped_sales.shift(28)

    # Rolling averages.
    # shift(1) is essential to prevent target leakage.
    for window in [7, 14, 28]:
        dataset[f"rolling_mean_{window}"] = (
            grouped_sales.transform(
                lambda values: (
                    values
                    .shift(1)
                    .rolling(
                        window=window,
                        min_periods=1,
                    )
                    .mean()
                )
            )
        )

    # =====================================================
    # Calendar features
    # =====================================================
    dataset["day_of_week"] = (
        dataset["sale_date"].dt.dayofweek
    )

    dataset["day_of_month"] = (
        dataset["sale_date"].dt.day
    )

    dataset["week_of_year"] = (
        dataset["sale_date"]
        .dt.isocalendar()
        .week
        .astype(int)
    )

    dataset["month"] = (
        dataset["sale_date"].dt.month
    )

    dataset["quarter"] = (
        dataset["sale_date"].dt.quarter
    )

    dataset["is_weekend"] = (
        dataset["day_of_week"] >= 5
    ).astype(int)

    # =====================================================
    # Trend feature
    # =====================================================
    minimum_date = dataset["sale_date"].min()

    dataset["days_since_start"] = (
        dataset["sale_date"] - minimum_date
    ).dt.days

    return dataset