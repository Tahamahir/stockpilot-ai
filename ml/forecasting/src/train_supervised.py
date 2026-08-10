from __future__ import annotations
from datetime import timedelta
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from src.build_dataset import (
    SERIES_COLUMNS,
    TARGET_COLUMN,
    build_forecasting_dataset,
)

from src.metrics import calculate_forecasting_metrics


# =========================================================
# Configuration
# =========================================================
TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    "http://localhost:5000",
)

EXPERIMENT_NAME = os.getenv(
    "MLFLOW_EXPERIMENT_NAME",
    "stockpilot-demand-forecasting",
)

TEST_HORIZON_DAYS = 30

RANDOM_STATE = 42


# Best baseline already measured
BASELINE_MAE = 3.020045
BASELINE_RMSE = 6.190249
BASELINE_WAPE = 50.257295


CATEGORICAL_FEATURES = [
    "tenant_id",
    "store_id",
    "product_id",
]


NUMERICAL_FEATURES = [
    "lag_1",
    "lag_7",
    "lag_14",
    "lag_28",

    "rolling_mean_7",
    "rolling_mean_14",
    "rolling_mean_28",

    "day_of_week",
    "day_of_month",
    "week_of_year",
    "month",
    "quarter",
    "is_weekend",
    "days_since_start",
]


FEATURE_COLUMNS = (
    CATEGORICAL_FEATURES
    + NUMERICAL_FEATURES
)


# =========================================================
# Plot
# =========================================================
def save_forecast_plot(
    results: pd.DataFrame,
    output_path: Path,
) -> None:
    """
    Save aggregate actual versus predicted demand.
    """

    daily_results = (
        results
        .groupby(
            "sale_date",
            as_index=False,
        )
        .agg(
            actual_quantity=(
                TARGET_COLUMN,
                "sum",
            ),
            predicted_quantity=(
                "prediction",
                "sum",
            ),
        )
    )

    figure, axis = plt.subplots(
        figsize=(12, 5)
    )

    axis.plot(
        daily_results["sale_date"],
        daily_results["actual_quantity"],
        label="Actual demand",
    )

    axis.plot(
        daily_results["sale_date"],
        daily_results["predicted_quantity"],
        label="Predicted demand",
    )

    axis.set_title(
        "StockPilot demand forecasting"
    )

    axis.set_xlabel("Date")
    axis.set_ylabel("Quantity sold")

    axis.legend()
    axis.grid(alpha=0.3)

    figure.tight_layout()

    figure.savefig(
        output_path,
        dpi=150,
    )

    plt.close(figure)


# =========================================================
# Training
# =========================================================
def train_supervised_model() -> None:
    """
    Train and evaluate a global supervised demand model.
    """

    mlflow.set_tracking_uri(
        TRACKING_URI
    )

    mlflow.set_experiment(
        EXPERIMENT_NAME
    )

    print(
        "Building forecasting dataset..."
    )

    dataset = (
    build_forecasting_dataset()
    )

    # Convert PostgreSQL UUID objects to strings.
    # This is required for MLflow model serialization
    # and keeps categorical identifiers consistent.
    for column in CATEGORICAL_FEATURES:
        dataset[column] = (
            dataset[column]
            .astype(str)
    )

    dataset = dataset.dropna(
        subset=FEATURE_COLUMNS
    ).copy()

    maximum_date = (
        dataset["sale_date"].max()
    )

    test_start_date = (
        maximum_date
        - timedelta(
            days=int(TEST_HORIZON_DAYS - 1)
        )
    )

    # =====================================================
    # Temporal split
    # =====================================================
    train_data = dataset[
        dataset["sale_date"]
        < test_start_date
    ].copy()

    test_data = dataset[
        dataset["sale_date"]
        >= test_start_date
    ].copy()

    print()
    print(
        f"Train period: "
        f"{train_data['sale_date'].min().date()} "
        f"-> "
        f"{train_data['sale_date'].max().date()}"
    )

    print(
        f"Test period: "
        f"{test_data['sale_date'].min().date()} "
        f"-> "
        f"{test_data['sale_date'].max().date()}"
    )

    print(
        f"Train rows: {len(train_data):,}"
    )

    print(
        f"Test rows: {len(test_data):,}"
    )

    # =====================================================
    # X / y
    # =====================================================
    X_train = train_data[
        FEATURE_COLUMNS
    ].copy()

    y_train = train_data[
        TARGET_COLUMN
    ].copy()

    X_test = test_data[
        FEATURE_COLUMNS
    ].copy()

    y_test = test_data[
        TARGET_COLUMN
    ].copy()

    # =====================================================
    # Preprocessing
    # =====================================================
    categorical_transformer = (
        OrdinalEncoder(
            handle_unknown="use_encoded_value",
            unknown_value=-1,
        )
    )

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                categorical_transformer,
                CATEGORICAL_FEATURES,
            ),
            (
                "numerical",
                "passthrough",
                NUMERICAL_FEATURES,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )

    # =====================================================
    # Model
    # =====================================================
    model = HistGradientBoostingRegressor(
        loss="poisson",

        learning_rate=0.08,

        max_iter=300,

        max_leaf_nodes=31,

        min_samples_leaf=40,

        l2_regularization=1.0,

        early_stopping=False,

        categorical_features=[
            0,
            1,
            2,
        ],

        random_state=RANDOM_STATE,
    )

    pipeline = Pipeline(
        steps=[
            (
                "preprocessor",
                preprocessor,
            ),
            (
                "model",
                model,
            ),
        ]
    )

    print()
    print(
        "Training HistGradientBoostingRegressor..."
    )

    pipeline.fit(
        X_train,
        y_train,
    )

    # =====================================================
    # Prediction
    # =====================================================
    predictions = pipeline.predict(
        X_test
    )

    predictions = np.clip(
        predictions,
        a_min=0,
        a_max=None,
    )

    metrics = (
        calculate_forecasting_metrics(
            y_true=y_test.to_numpy(),
            y_pred=predictions,
        )
    )

    # =====================================================
    # Compare against baseline
    # =====================================================
    mae_improvement = (
        (
            BASELINE_MAE
            - metrics["mae"]
        )
        / BASELINE_MAE
        * 100
    )

    rmse_improvement = (
        (
            BASELINE_RMSE
            - metrics["rmse"]
        )
        / BASELINE_RMSE
        * 100
    )

    wape_improvement = (
        (
            BASELINE_WAPE
            - metrics[
                "wape_percentage"
            ]
        )
        / BASELINE_WAPE
        * 100
    )

    comparison_metrics = {
        **metrics,

        "mae_improvement_vs_baseline_pct":
            float(mae_improvement),

        "rmse_improvement_vs_baseline_pct":
            float(rmse_improvement),

        "wape_improvement_vs_baseline_pct":
            float(wape_improvement),
    }

    print()
    print("Supervised model results")

    for metric_name, value in (
        comparison_metrics.items()
    ):
        print(
            f"{metric_name}: "
            f"{value:.4f}"
        )

    # =====================================================
    # MLflow
    # =====================================================
    run_name = (
        "hist_gradient_boosting_poisson_"
        f"{maximum_date.date()}"
    )

    with mlflow.start_run(
        run_name=run_name
    ):

        mlflow.log_params(
            {
                "model_type":
                    "HistGradientBoostingRegressor",

                "loss":
                    "poisson",

                "learning_rate":
                    0.08,

                "max_iter":
                    300,

                "max_leaf_nodes":
                    31,

                "min_samples_leaf":
                    40,

                "l2_regularization":
                    1.0,

                "test_horizon_days":
                    TEST_HORIZON_DAYS,

                "test_start_date":
                    str(
                        test_start_date.date()
                    ),

                "test_end_date":
                    str(
                        maximum_date.date()
                    ),

                "train_rows":
                    len(train_data),

                "test_rows":
                    len(test_data),

                "feature_count":
                    len(FEATURE_COLUMNS),

                "number_of_series":
                    dataset[
                        SERIES_COLUMNS
                    ]
                    .drop_duplicates()
                    .shape[0],
            }
        )

        mlflow.log_metrics(
            comparison_metrics
        )

        # =================================================
        # Predictions artifact
        # =================================================
        results = test_data[
            [
                "sale_date",
                *SERIES_COLUMNS,
                TARGET_COLUMN,
            ]
        ].copy()

        results["prediction"] = (
            predictions
        )

        results[
            "absolute_error"
        ] = np.abs(
            results[TARGET_COLUMN]
            - results["prediction"]
        )

        with TemporaryDirectory() as directory:

            artifact_directory = Path(
                directory
            )

            predictions_path = (
                artifact_directory
                / "supervised_predictions.csv"
            )

            plot_path = (
                artifact_directory
                / "supervised_forecast.png"
            )

            results.to_csv(
                predictions_path,
                index=False,
            )

            save_forecast_plot(
                results,
                plot_path,
            )

            mlflow.log_artifact(
                str(predictions_path),
                artifact_path="predictions",
            )

            mlflow.log_artifact(
                str(plot_path),
                artifact_path="figures",
            )

        # =================================================
        # Model
        # =================================================
        input_example = X_test.head(20).copy()

        for column in NUMERICAL_FEATURES:
            input_example[column] = (
            input_example[column]
            .astype("float64")
        )

        mlflow.sklearn.log_model(
            sk_model=pipeline,
            name="demand_forecasting_model",
            input_example=input_example,
            serialization_format="cloudpickle",
        )

    print()
    print(
        "Model successfully logged to MLflow."
    )


if __name__ == "__main__":
    train_supervised_model()