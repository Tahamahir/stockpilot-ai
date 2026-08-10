from __future__ import annotations

import os
import uuid
from datetime import timedelta

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd

from mlflow import MlflowClient
from sqlalchemy import text

from src.backtest_supervised import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERICAL_FEATURES,
)

from src.build_dataset import (
    SERIES_COLUMNS,
    TARGET_COLUMN,
    build_forecasting_dataset,
)

from src.database import get_engine


# =========================================================
# Configuration
# =========================================================

TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    "http://localhost:5000",
)

REGISTERED_MODEL_NAME = (
    "stockpilot-demand-forecasting-model"
)

MODEL_ALIAS = "candidate"

FORECAST_HORIZON_DAYS = 30


# =========================================================
# Historical demand
# =========================================================

def build_history_dictionary(
    dataset: pd.DataFrame,
) -> dict[tuple[str, str, str], list[float]]:
    """
    Store historical demand for every
    tenant-store-product series.

    The list will later be extended with predictions,
    allowing recursive forecasting.
    """

    history: dict[
        tuple[str, str, str],
        list[float],
    ] = {}

    ordered_dataset = dataset.sort_values(
        SERIES_COLUMNS + ["sale_date"]
    )

    grouped = ordered_dataset.groupby(
        SERIES_COLUMNS,
        sort=False,
    )

    for key, group in grouped:

        series_key = tuple(
            str(value)
            for value in key
        )

        history[series_key] = (
            group[TARGET_COLUMN]
            .astype(float)
            .tolist()
        )

    return history


# =========================================================
# Recursive forecasting
# =========================================================

def generate_recursive_forecasts(
    model,
    dataset: pd.DataFrame,
) -> pd.DataFrame:
    """
    Generate a true 30-day future forecast.

    Predictions from previous future days are reused
    to calculate future lags and rolling averages.
    """

    dataset = dataset.copy()

    # UUID objects -> strings
    for column in CATEGORICAL_FEATURES:
        dataset[column] = (
            dataset[column]
            .astype(str)
        )

    dataset = dataset.sort_values(
        SERIES_COLUMNS + ["sale_date"]
    ).reset_index(drop=True)

    origin_date = (
        dataset["sale_date"].min()
    )

    training_end_date = (
        dataset["sale_date"].max()
    )

    series = (
        dataset[
            SERIES_COLUMNS
        ]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    history = build_history_dictionary(
        dataset
    )

    forecast_rows: list[
        dict[str, object]
    ] = []

    print()
    print(
        f"Historical data ends: "
        f"{training_end_date.date()}"
    )

    print(
        f"Number of series: "
        f"{len(series)}"
    )

    print(
        f"Forecast horizon: "
        f"{FORECAST_HORIZON_DAYS} days"
    )

    # =====================================================
    # Forecast day by day
    # =====================================================

    for horizon_day in range(
        1,
        FORECAST_HORIZON_DAYS + 1,
    ):

        forecast_date = (
            training_end_date
            + timedelta(
                days=horizon_day
            )
        )

        feature_rows = []

        series_keys = []

        for series_values in series.itertuples(
            index=False,
            name=None,
        ):

            key = tuple(
                str(value)
                for value in series_values
            )

            values = history[key]

            if len(values) < 28:
                raise RuntimeError(
                    f"Not enough history "
                    f"for series {key}"
                )

            lag_1 = values[-1]
            lag_7 = values[-7]
            lag_14 = values[-14]
            lag_28 = values[-28]

            rolling_mean_7 = float(
                np.mean(
                    values[-7:]
                )
            )

            rolling_mean_14 = float(
                np.mean(
                    values[-14:]
                )
            )

            rolling_mean_28 = float(
                np.mean(
                    values[-28:]
                )
            )

            day_of_week = (
                forecast_date.dayofweek
            )

            day_of_month = (
                forecast_date.day
            )

            week_of_year = int(
                forecast_date
                .isocalendar()
                .week
            )

            month = (
                forecast_date.month
            )

            quarter = (
                forecast_date.quarter
            )

            is_weekend = int(
                day_of_week >= 5
            )

            days_since_start = (
                forecast_date
                - origin_date
            ).days

            feature_rows.append(
                {
                    "tenant_id":
                        key[0],

                    "store_id":
                        key[1],

                    "product_id":
                        key[2],

                    "lag_1":
                        lag_1,

                    "lag_7":
                        lag_7,

                    "lag_14":
                        lag_14,

                    "lag_28":
                        lag_28,

                    "rolling_mean_7":
                        rolling_mean_7,

                    "rolling_mean_14":
                        rolling_mean_14,

                    "rolling_mean_28":
                        rolling_mean_28,

                    "day_of_week":
                        day_of_week,

                    "day_of_month":
                        day_of_month,

                    "week_of_year":
                        week_of_year,

                    "month":
                        month,

                    "quarter":
                        quarter,

                    "is_weekend":
                        is_weekend,

                    "days_since_start":
                        days_since_start,
                }
            )

            series_keys.append(
                key
            )

        features = pd.DataFrame(
            feature_rows
        )

        # Keep feature types compatible with
        # the model signature used in MLflow.
        for column in NUMERICAL_FEATURES:
            features[column] = (
                pd.to_numeric(
                    features[column]
                )
                .astype("float64")
            )

        predictions = model.predict(
            features[
                FEATURE_COLUMNS
            ]
        )

        predictions = np.clip(
            predictions,
            a_min=0,
            a_max=None,
        )

        # =================================================
        # Prediction becomes history for next future day
        # =================================================

        for key, prediction in zip(
            series_keys,
            predictions,
        ):

            prediction_value = float(
                prediction
            )

            history[key].append(
                prediction_value
            )

            forecast_rows.append(
                {
                    "forecast_date":
                        forecast_date.date(),

                    "horizon_day":
                        horizon_day,

                    "tenant_id":
                        key[0],

                    "store_id":
                        key[1],

                    "product_id":
                        key[2],

                    "predicted_quantity":
                        prediction_value,
                }
            )

        print(
            f"Day {horizon_day:02d} | "
            f"{forecast_date.date()} | "
            f"forecast quantity = "
            f"{predictions.sum():,.2f}"
        )

    return pd.DataFrame(
        forecast_rows
    )


# =========================================================
# PostgreSQL persistence
# =========================================================

def persist_forecasts(
    forecasts: pd.DataFrame,
    model_version: int,
    source_training_run_id: str | None,
    training_end_date,
) -> str:
    """
    Save one forecasting run and its predictions.
    """

    forecast_run_id = str(
        uuid.uuid4()
    )

    engine = get_engine()

    forecast_start_date = (
        forecasts[
            "forecast_date"
        ].min()
    )

    forecast_end_date = (
        forecasts[
            "forecast_date"
        ].max()
    )

    number_of_series = (
        forecasts[
            SERIES_COLUMNS
        ]
        .drop_duplicates()
        .shape[0]
    )

    # =====================================================
    # Create run
    # =====================================================

    insert_run_query = text(
        """
        INSERT INTO ml.forecast_runs (
            forecast_run_id,
            model_name,
            model_version,
            model_alias,
            source_training_run_id,
            training_end_date,
            forecast_start_date,
            forecast_end_date,
            horizon_days,
            number_of_series,
            status
        )
        VALUES (
            CAST(:forecast_run_id AS UUID),
            :model_name,
            :model_version,
            :model_alias,
            :source_training_run_id,
            :training_end_date,
            :forecast_start_date,
            :forecast_end_date,
            :horizon_days,
            :number_of_series,
            'running'
        )
        """
    )

    with engine.begin() as connection:

        connection.execute(
            insert_run_query,
            {
                "forecast_run_id":
                    forecast_run_id,

                "model_name":
                    REGISTERED_MODEL_NAME,

                "model_version":
                    model_version,

                "model_alias":
                    MODEL_ALIAS,

                "source_training_run_id":
                    source_training_run_id,

                "training_end_date":
                    training_end_date,

                "forecast_start_date":
                    forecast_start_date,

                "forecast_end_date":
                    forecast_end_date,

                "horizon_days":
                    FORECAST_HORIZON_DAYS,

                "number_of_series":
                    number_of_series,
            },
        )

    # =====================================================
    # Prepare predictions
    # =====================================================

    records = []

    for row in forecasts.itertuples(
        index=False
    ):

        records.append(
            {
                "forecast_run_id":
                    forecast_run_id,

                "forecast_date":
                    row.forecast_date,

                "horizon_day":
                    int(
                        row.horizon_day
                    ),

                "tenant_id":
                    str(
                        row.tenant_id
                    ),

                "store_id":
                    str(
                        row.store_id
                    ),

                "product_id":
                    str(
                        row.product_id
                    ),

                "predicted_quantity":
                    float(
                        row.predicted_quantity
                    ),
            }
        )

    insert_forecast_query = text(
        """
        INSERT INTO ml.demand_forecasts (
            forecast_run_id,
            forecast_date,
            horizon_day,
            tenant_id,
            store_id,
            product_id,
            predicted_quantity
        )
        VALUES (
            CAST(:forecast_run_id AS UUID),
            :forecast_date,
            :horizon_day,
            CAST(:tenant_id AS UUID),
            CAST(:store_id AS UUID),
            CAST(:product_id AS UUID),
            :predicted_quantity
        )
        """
    )

    try:

        with engine.begin() as connection:

            connection.execute(
                insert_forecast_query,
                records,
            )

            connection.execute(
                text(
                    """
                    UPDATE ml.forecast_runs
                    SET status = 'completed'
                    WHERE forecast_run_id =
                        CAST(:forecast_run_id AS UUID)
                    """
                ),
                {
                    "forecast_run_id":
                        forecast_run_id
                },
            )

    except Exception:

        with engine.begin() as connection:

            connection.execute(
                text(
                    """
                    UPDATE ml.forecast_runs
                    SET status = 'failed'
                    WHERE forecast_run_id =
                        CAST(:forecast_run_id AS UUID)
                    """
                ),
                {
                    "forecast_run_id":
                        forecast_run_id
                },
            )

        raise

    return forecast_run_id


# =========================================================
# Main
# =========================================================

def main() -> None:

    mlflow.set_tracking_uri(
        TRACKING_URI
    )

    print(
        "Loading candidate model "
        "from MLflow..."
    )

    model_uri = (
        f"models:/"
        f"{REGISTERED_MODEL_NAME}"
        f"@{MODEL_ALIAS}"
    )

    model = mlflow.sklearn.load_model(
        model_uri
    )

    client = MlflowClient()

    model_version_info = (
        client.get_model_version_by_alias(
            name=REGISTERED_MODEL_NAME,
            alias=MODEL_ALIAS,
        )
    )

    model_version = int(
        model_version_info.version
    )

    source_training_run_id = getattr(
        model_version_info,
        "run_id",
        None,
    )

    print(
        f"Model loaded: "
        f"{REGISTERED_MODEL_NAME}"
    )

    print(
        f"Version: "
        f"{model_version}"
    )

    print(
        f"Alias: "
        f"{MODEL_ALIAS}"
    )

    # =====================================================
    # Historical dataset
    # =====================================================

    dataset = (
        build_forecasting_dataset()
    )

    training_end_date = (
        dataset[
            "sale_date"
        ]
        .max()
        .date()
    )

    # =====================================================
    # Forecast
    # =====================================================

    forecasts = (
        generate_recursive_forecasts(
            model=model,
            dataset=dataset,
        )
    )

    # =====================================================
    # Validation
    # =====================================================

    expected_rows = (
        forecasts[
            SERIES_COLUMNS
        ]
        .drop_duplicates()
        .shape[0]
        * FORECAST_HORIZON_DAYS
    )

    if len(forecasts) != expected_rows:

        raise RuntimeError(
            f"Unexpected forecast count. "
            f"Expected {expected_rows}, "
            f"received {len(forecasts)}."
        )

    if (
        forecasts[
            "predicted_quantity"
        ]
        < 0
    ).any():

        raise RuntimeError(
            "Negative forecasts detected."
        )

    # =====================================================
    # Persist
    # =====================================================

    forecast_run_id = (
        persist_forecasts(
            forecasts=forecasts,
            model_version=model_version,
            source_training_run_id=(
                source_training_run_id
            ),
            training_end_date=(
                training_end_date
            ),
        )
    )

    # =====================================================
    # Final summary
    # =====================================================

    print()
    print("=" * 70)
    print("FORECAST GENERATION COMPLETED")
    print("=" * 70)

    print(
        f"Forecast run ID: "
        f"{forecast_run_id}"
    )

    print(
        f"Model version: "
        f"{model_version}"
    )

    print(
        f"Forecast start: "
        f"{forecasts['forecast_date'].min()}"
    )

    print(
        f"Forecast end: "
        f"{forecasts['forecast_date'].max()}"
    )

    print(
        f"Forecast rows: "
        f"{len(forecasts):,}"
    )

    print(
        "Number of series: "
        f"{forecasts[SERIES_COLUMNS].drop_duplicates().shape[0]}"
    )

    print(
        "Total forecast quantity: "
        f"{forecasts['predicted_quantity'].sum():,.2f}"
    )


if __name__ == "__main__":
    main()