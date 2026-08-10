from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import mlflow
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

HORIZON_DAYS = 30

NUMBER_OF_FOLDS = 4

RANDOM_STATE = 42


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
# Model
# =========================================================

def build_pipeline() -> Pipeline:
    """
    Build the exact same model used in train_supervised.py.
    """

    categorical_transformer = OrdinalEncoder(
        handle_unknown="use_encoded_value",
        unknown_value=-1,
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

    model = HistGradientBoostingRegressor(
        loss="poisson",
        learning_rate=0.08,
        max_iter=300,
        max_leaf_nodes=31,
        min_samples_leaf=40,
        l2_regularization=1.0,
        early_stopping=False,
        categorical_features=[0, 1, 2],
        random_state=RANDOM_STATE,
    )

    return Pipeline(
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


# =========================================================
# Backtesting
# =========================================================

def run_backtest() -> None:
    """
    Run expanding-window temporal backtesting.

    Four consecutive 30-day evaluation windows are used.
    For every fold:
      - train only on dates before the evaluation window
      - evaluate the supervised model
      - evaluate the 28-day moving-average baseline
      - compare both models
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

    dataset = build_forecasting_dataset()

    # Convert UUID values returned by PostgreSQL
    # to strings for sklearn / MLflow compatibility.
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

    print()
    print(
        f"Dataset period: "
        f"{dataset['sale_date'].min().date()} "
        f"-> {maximum_date.date()}"
    )

    print(
        f"Dataset rows: {len(dataset):,}"
    )

    print(
        "Number of series: "
        f"{dataset[SERIES_COLUMNS].drop_duplicates().shape[0]}"
    )

    # -----------------------------------------------------
    # Fold offsets
    #
    # With max date 2025-12-30:
    #
    # fold 1: 2025-09-02 -> 2025-10-01
    # fold 2: 2025-10-02 -> 2025-10-31
    # fold 3: 2025-11-01 -> 2025-11-30
    # fold 4: 2025-12-01 -> 2025-12-30
    # -----------------------------------------------------

    offsets = list(
        range(
            (NUMBER_OF_FOLDS - 1)
            * HORIZON_DAYS,
            -1,
            -HORIZON_DAYS,
        )
    )

    backtest_results = []

    parent_run_name = (
        "hist_gradient_boosting_backtest_"
        f"{maximum_date.date()}"
    )

    with mlflow.start_run(
        run_name=parent_run_name
    ):

        mlflow.log_params(
            {
                "model_type":
                    "HistGradientBoostingRegressor",

                "validation_strategy":
                    "expanding_window",

                "number_of_folds":
                    NUMBER_OF_FOLDS,

                "horizon_days":
                    HORIZON_DAYS,

                "baseline":
                    "moving_average_28_days",

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

        # =================================================
        # Folds
        # =================================================

        for fold_number, offset_days in enumerate(
            offsets,
            start=1,
        ):

            test_end_date = (
                maximum_date
                - timedelta(
                    days=int(offset_days)
                )
            )

            test_start_date = (
                test_end_date
                - timedelta(
                    days=HORIZON_DAYS - 1
                )
            )

            train_data = dataset[
                dataset["sale_date"]
                < test_start_date
            ].copy()

            test_data = dataset[
                (
                    dataset["sale_date"]
                    >= test_start_date
                )
                &
                (
                    dataset["sale_date"]
                    <= test_end_date
                )
            ].copy()

            if train_data.empty:
                raise RuntimeError(
                    f"Fold {fold_number}: "
                    "training dataset is empty."
                )

            if test_data.empty:
                raise RuntimeError(
                    f"Fold {fold_number}: "
                    "test dataset is empty."
                )

            print()
            print(
                "=" * 70
            )

            print(
                f"FOLD {fold_number}"
            )

            print(
                f"Train: "
                f"{train_data['sale_date'].min().date()} "
                f"-> "
                f"{train_data['sale_date'].max().date()}"
            )

            print(
                f"Test : "
                f"{test_start_date.date()} "
                f"-> "
                f"{test_end_date.date()}"
            )

            print(
                f"Train rows: "
                f"{len(train_data):,}"
            )

            print(
                f"Test rows: "
                f"{len(test_data):,}"
            )

            # =============================================
            # Train supervised model
            # =============================================

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

            pipeline = build_pipeline()

            print(
                "Training model..."
            )

            pipeline.fit(
                X_train,
                y_train,
            )

            predictions = pipeline.predict(
                X_test
            )

            predictions = np.clip(
                predictions,
                a_min=0,
                a_max=None,
            )

            model_metrics = (
                calculate_forecasting_metrics(
                    y_true=y_test.to_numpy(),
                    y_pred=predictions,
                )
            )

            # =============================================
            # Baseline
            # =============================================

            baseline_predictions = (
                test_data[
                    "rolling_mean_28"
                ]
                .to_numpy()
            )

            baseline_predictions = np.clip(
                baseline_predictions,
                a_min=0,
                a_max=None,
            )

            baseline_metrics = (
                calculate_forecasting_metrics(
                    y_true=y_test.to_numpy(),
                    y_pred=baseline_predictions,
                )
            )

            # =============================================
            # Improvement
            # =============================================

            wape_improvement = (
                (
                    baseline_metrics[
                        "wape_percentage"
                    ]
                    - model_metrics[
                        "wape_percentage"
                    ]
                )
                /
                baseline_metrics[
                    "wape_percentage"
                ]
                * 100
            )

            mae_improvement = (
                (
                    baseline_metrics["mae"]
                    - model_metrics["mae"]
                )
                /
                baseline_metrics["mae"]
                * 100
            )

            rmse_improvement = (
                (
                    baseline_metrics["rmse"]
                    - model_metrics["rmse"]
                )
                /
                baseline_metrics["rmse"]
                * 100
            )

            model_wins = (
                model_metrics[
                    "wape_percentage"
                ]
                <
                baseline_metrics[
                    "wape_percentage"
                ]
            )

            print()
            print(
                "Supervised model"
            )

            print(
                f"  MAE  : "
                f"{model_metrics['mae']:.4f}"
            )

            print(
                f"  RMSE : "
                f"{model_metrics['rmse']:.4f}"
            )

            print(
                f"  WAPE : "
                f"{model_metrics['wape_percentage']:.4f}%"
            )

            print()
            print(
                "Moving-average baseline"
            )

            print(
                f"  MAE  : "
                f"{baseline_metrics['mae']:.4f}"
            )

            print(
                f"  RMSE : "
                f"{baseline_metrics['rmse']:.4f}"
            )

            print(
                f"  WAPE : "
                f"{baseline_metrics['wape_percentage']:.4f}%"
            )

            print()
            print(
                f"WAPE improvement: "
                f"{wape_improvement:.2f}%"
            )

            # =============================================
            # MLflow child run
            # =============================================

            with mlflow.start_run(
                run_name=(
                    f"backtest_fold_{fold_number}_"
                    f"{test_start_date.date()}_"
                    f"{test_end_date.date()}"
                ),
                nested=True,
            ):

                mlflow.log_params(
                    {
                        "fold":
                            fold_number,

                        "train_start":
                            str(
                                train_data[
                                    "sale_date"
                                ]
                                .min()
                                .date()
                            ),

                        "train_end":
                            str(
                                train_data[
                                    "sale_date"
                                ]
                                .max()
                                .date()
                            ),

                        "test_start":
                            str(
                                test_start_date.date()
                            ),

                        "test_end":
                            str(
                                test_end_date.date()
                            ),

                        "train_rows":
                            len(train_data),

                        "test_rows":
                            len(test_data),
                    }
                )

                mlflow.log_metrics(
                    {
                        "model_mae":
                            model_metrics["mae"],

                        "model_rmse":
                            model_metrics["rmse"],

                        "model_wape":
                            model_metrics[
                                "wape_percentage"
                            ],

                        "baseline_mae":
                            baseline_metrics["mae"],

                        "baseline_rmse":
                            baseline_metrics["rmse"],

                        "baseline_wape":
                            baseline_metrics[
                                "wape_percentage"
                            ],

                        "mae_improvement_pct":
                            mae_improvement,

                        "rmse_improvement_pct":
                            rmse_improvement,

                        "wape_improvement_pct":
                            wape_improvement,

                        "model_wins":
                            float(model_wins),
                    }
                )

            backtest_results.append(
                {
                    "fold":
                        fold_number,

                    "test_start":
                        test_start_date.date(),

                    "test_end":
                        test_end_date.date(),

                    "model_mae":
                        model_metrics["mae"],

                    "model_rmse":
                        model_metrics["rmse"],

                    "model_wape":
                        model_metrics[
                            "wape_percentage"
                        ],

                    "baseline_mae":
                        baseline_metrics["mae"],

                    "baseline_rmse":
                        baseline_metrics["rmse"],

                    "baseline_wape":
                        baseline_metrics[
                            "wape_percentage"
                        ],

                    "wape_improvement_pct":
                        wape_improvement,

                    "model_wins":
                        model_wins,
                }
            )

        # =================================================
        # Global backtest summary
        # =================================================

        summary = pd.DataFrame(
            backtest_results
        )

        average_model_mae = (
            summary[
                "model_mae"
            ].mean()
        )

        average_model_rmse = (
            summary[
                "model_rmse"
            ].mean()
        )

        average_model_wape = (
            summary[
                "model_wape"
            ].mean()
        )

        average_baseline_wape = (
            summary[
                "baseline_wape"
            ].mean()
        )

        average_wape_improvement = (
            summary[
                "wape_improvement_pct"
            ].mean()
        )

        wape_std = (
            summary[
                "model_wape"
            ].std()
        )

        folds_won = int(
            summary[
                "model_wins"
            ].sum()
        )

        mlflow.log_metrics(
            {
                "backtest_mean_mae":
                    float(
                        average_model_mae
                    ),

                "backtest_mean_rmse":
                    float(
                        average_model_rmse
                    ),

                "backtest_mean_wape":
                    float(
                        average_model_wape
                    ),

                "backtest_wape_std":
                    float(
                        wape_std
                    ),

                "baseline_mean_wape":
                    float(
                        average_baseline_wape
                    ),

                "mean_wape_improvement_pct":
                    float(
                        average_wape_improvement
                    ),

                "folds_won":
                    float(
                        folds_won
                    ),
            }
        )

        with TemporaryDirectory() as directory:

            summary_path = (
                Path(directory)
                / "backtest_summary.csv"
            )

            summary.to_csv(
                summary_path,
                index=False,
            )

            mlflow.log_artifact(
                str(summary_path),
                artifact_path="backtesting",
            )

    # =====================================================
    # Console summary
    # =====================================================

    print()
    print(
        "=" * 70
    )

    print(
        "BACKTEST SUMMARY"
    )

    print(
        "=" * 70
    )

    print(
        summary.to_string(
            index=False
        )
    )

    print()

    print(
        f"Average supervised MAE: "
        f"{average_model_mae:.4f}"
    )

    print(
        f"Average supervised RMSE: "
        f"{average_model_rmse:.4f}"
    )

    print(
        f"Average supervised WAPE: "
        f"{average_model_wape:.4f}%"
    )

    print(
        f"Average baseline WAPE: "
        f"{average_baseline_wape:.4f}%"
    )

    print(
        f"Average WAPE improvement: "
        f"{average_wape_improvement:.2f}%"
    )

    print(
        f"WAPE standard deviation: "
        f"{wape_std:.4f}"
    )

    print(
        f"Folds won against baseline: "
        f"{folds_won}/{NUMBER_OF_FOLDS}"
    )


if __name__ == "__main__":
    run_backtest()