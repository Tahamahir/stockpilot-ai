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
    Build a complete daily time series for each store-product pair.

    Missing sales dates are interpreted as zero sales.
    Lag and rolling features use only historical observations.
    """

    sales = load_daily_sales()

    if sales.empty:
        raise RuntimeError(
            "analytics.fct_daily_sales does not contain any data."
        )

    sales["sale_date"] = pd.to_datetime(
        sales["sale_date"],
        errors="raise",
    )

    sales[TARGET_COLUMN] = pd.to_numeric(
        sales[TARGET_COLUMN],
        errors="coerce",
    ).fillna(0.0)

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

    dataset[TARGET_COLUMN] = (
        dataset[TARGET_COLUMN]
        .fillna(0.0)
        .astype(float)
    )

    dataset = dataset.sort_values(
        SERIES_COLUMNS + ["sale_date"]
    ).reset_index(drop=True)

    grouped_sales = dataset.groupby(
        SERIES_COLUMNS,
        sort=False,
    )[TARGET_COLUMN]

    dataset["lag_7"] = grouped_sales.shift(7)
    dataset["lag_28"] = grouped_sales.shift(28)

    dataset["rolling_mean_7"] = grouped_sales.transform(
        lambda values: (
            values.shift(1)
            .rolling(
                window=7,
                min_periods=1,
            )
            .mean()
        )
    )

    dataset["rolling_mean_28"] = grouped_sales.transform(
        lambda values: (
            values.shift(1)
            .rolling(
                window=28,
                min_periods=1,
            )
            .mean()
        )
    )

    dataset["day_of_week"] = (
        dataset["sale_date"].dt.dayofweek
    )

    dataset["month"] = (
        dataset["sale_date"].dt.month
    )

    dataset["is_weekend"] = (
        dataset["day_of_week"] >= 5
    ).astype(int)

    return dataset