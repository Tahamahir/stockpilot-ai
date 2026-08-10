from __future__ import annotations

import os

import mlflow
import mlflow.sklearn
from mlflow import MlflowClient

from src.build_dataset import (
    SERIES_COLUMNS,
    TARGET_COLUMN,
    build_forecasting_dataset,
)

from src.backtest_supervised import (
    CATEGORICAL_FEATURES,
    NUMERICAL_FEATURES,
    FEATURE_COLUMNS,
    build_pipeline,
)


TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    "http://localhost:5000",
)

EXPERIMENT_NAME = os.getenv(
    "MLFLOW_EXPERIMENT_NAME",
    "stockpilot-demand-forecasting",
)

REGISTERED_MODEL_NAME = (
    "stockpilot-demand-forecasting-model"
)


# Backtesting results already validated
BACKTEST_MEAN_WAPE = 44.2790
BACKTEST_BASELINE_WAPE = 48.7978
BACKTEST_IMPROVEMENT = 9.23
BACKTEST_FOLDS_WON = 4


def train_final_model() -> None:

    mlflow.set_tracking_uri(
        TRACKING_URI
    )

    mlflow.set_experiment(
        EXPERIMENT_NAME
    )

    print(
        "Building final forecasting dataset..."
    )

    dataset = (
        build_forecasting_dataset()
    )

    # PostgreSQL UUID -> string
    for column in CATEGORICAL_FEATURES:
        dataset[column] = (
            dataset[column]
            .astype(str)
        )

    dataset = dataset.dropna(
        subset=FEATURE_COLUMNS
    ).copy()

    minimum_date = (
        dataset["sale_date"]
        .min()
    )

    maximum_date = (
        dataset["sale_date"]
        .max()
    )

    print(
        f"Training period: "
        f"{minimum_date.date()} "
        f"-> "
        f"{maximum_date.date()}"
    )

    print(
        f"Training rows: "
        f"{len(dataset):,}"
    )

    number_of_series = (
        dataset[
            SERIES_COLUMNS
        ]
        .drop_duplicates()
        .shape[0]
    )

    print(
        f"Number of series: "
        f"{number_of_series}"
    )

    # =====================================================
    # Features / target
    # =====================================================

    X = dataset[
        FEATURE_COLUMNS
    ].copy()

    y = dataset[
        TARGET_COLUMN
    ].copy()

    # =====================================================
    # Final model
    # =====================================================

    pipeline = build_pipeline()

    print()
    print(
        "Training final model "
        "on all available history..."
    )

    pipeline.fit(
        X,
        y,
    )

    # =====================================================
    # MLflow-compatible input example
    # =====================================================

    input_example = (
        X.tail(20).copy()
    )

    for column in NUMERICAL_FEATURES:
        input_example[column] = (
            input_example[column]
            .astype("float64")
        )

    # =====================================================
    # MLflow
    # =====================================================

    run_name = (
        "final_hist_gradient_boosting_"
        f"{maximum_date.date()}"
    )

    with mlflow.start_run(
        run_name=run_name
    ) as run:

        mlflow.log_params(
            {
                "model_type":
                    "HistGradientBoostingRegressor",

                "training_strategy":
                    "full_history_after_backtesting",

                "training_start":
                    str(
                        minimum_date.date()
                    ),

                "training_end":
                    str(
                        maximum_date.date()
                    ),

                "training_rows":
                    len(dataset),

                "number_of_series":
                    number_of_series,

                "feature_count":
                    len(FEATURE_COLUMNS),

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
            }
        )

        # Backtesting validation metrics
        mlflow.log_metrics(
            {
                "validated_backtest_mean_wape":
                    BACKTEST_MEAN_WAPE,

                "validated_baseline_mean_wape":
                    BACKTEST_BASELINE_WAPE,

                "validated_improvement_pct":
                    BACKTEST_IMPROVEMENT,

                "validated_folds_won":
                    float(
                        BACKTEST_FOLDS_WON
                    ),
            }
        )

        print()
        print(
            "Logging and registering "
            "final model..."
        )

        mlflow.sklearn.log_model(
            sk_model=pipeline,

            name=(
                "demand_forecasting_model"
            ),

            registered_model_name=(
                REGISTERED_MODEL_NAME
            ),

            input_example=input_example,

            serialization_format=(
                "cloudpickle"
            ),
        )

        run_id = run.info.run_id

    # =====================================================
    # Find latest registered version
    # =====================================================

    client = MlflowClient()

    versions = (
        client.search_model_versions(
            filter_string=(
                f"name='{REGISTERED_MODEL_NAME}'"
            )
        )
    )

    if not versions:
        raise RuntimeError(
            "No registered model version found."
        )

    latest_version = max(
        versions,
        key=lambda version: int(
            version.version
        ),
    )

    # =====================================================
    # Candidate alias
    # =====================================================

    client.set_registered_model_alias(
        name=REGISTERED_MODEL_NAME,
        alias="candidate",
        version=latest_version.version,
    )

    client.set_model_version_tag(
        name=REGISTERED_MODEL_NAME,
        version=latest_version.version,
        key="validation_status",
        value="backtest_passed",
    )

    client.set_model_version_tag(
        name=REGISTERED_MODEL_NAME,
        version=latest_version.version,
        key="folds_won",
        value="4/4",
    )

    client.set_model_version_tag(
        name=REGISTERED_MODEL_NAME,
        version=latest_version.version,
        key="mean_wape",
        value=str(
            BACKTEST_MEAN_WAPE
        ),
    )

    print()
    print("=" * 70)
    print("FINAL MODEL READY")
    print("=" * 70)

    print(
        f"Run ID: {run_id}"
    )

    print(
        f"Registered model: "
        f"{REGISTERED_MODEL_NAME}"
    )

    print(
        f"Version: "
        f"{latest_version.version}"
    )

    print(
        "Alias: candidate"
    )

    print(
        f"Training end date: "
        f"{maximum_date.date()}"
    )

    print(
        f"Backtest mean WAPE: "
        f"{BACKTEST_MEAN_WAPE:.4f}%"
    )


if __name__ == "__main__":
    train_final_model()