from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import matplotlib.pyplot as plt
import mlflow
import pandas as pd

from src.build_dataset import (
    SERIES_COLUMNS,
    TARGET_COLUMN,
    build_forecasting_dataset,
)
from src.metrics import calculate_forecasting_metrics


EXPERIMENT_NAME = os.getenv(
    "MLFLOW_EXPERIMENT_NAME",
    "stockpilot-demand-forecasting",
)

TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    "http://localhost:5000",
)

TEST_HORIZON_DAYS = 30

BASELINES = {
    "seasonal_naive_7_days": "lag_7",
    "seasonal_naive_28_days": "lag_28",
    "moving_average_28_days": "rolling_mean_28",
}


def save_aggregate_plot(
    predictions: pd.DataFrame,
    prediction_column: str,
    output_path: Path,
) -> None:
    """Save an actual versus predicted aggregate demand plot."""

    daily_results = (
        predictions
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
                prediction_column,
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
        "Aggregate demand: actual versus baseline forecast"
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


def run_baseline_experiments() -> None:
    """Evaluate and log the first StockPilot forecasting baselines."""

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    dataset = build_forecasting_dataset()

    maximum_date = dataset["sale_date"].max()

    test_start_date = (
        maximum_date
        - pd.Timedelta(
            days=TEST_HORIZON_DAYS - 1
        )
    )

    test_dataset = dataset[
        dataset["sale_date"] >= test_start_date
    ].copy()

    summary_rows: list[dict[str, object]] = []

    for baseline_name, prediction_column in BASELINES.items():
        evaluation_data = test_dataset.dropna(
            subset=[
                TARGET_COLUMN,
                prediction_column,
            ]
        ).copy()

        evaluation_data[prediction_column] = (
            evaluation_data[prediction_column]
            .clip(lower=0)
        )

        metrics = calculate_forecasting_metrics(
            y_true=evaluation_data[
                TARGET_COLUMN
            ].to_numpy(),
            y_pred=evaluation_data[
                prediction_column
            ].to_numpy(),
        )

        run_name = (
            f"{baseline_name}_"
            f"{maximum_date.date()}"
        )

        with mlflow.start_run(
            run_name=run_name
        ):
            mlflow.log_params(
                {
                    "model_type": "baseline",
                    "baseline_name": baseline_name,
                    "prediction_column": prediction_column,
                    "test_horizon_days": TEST_HORIZON_DAYS,
                    "test_start_date": str(
                        test_start_date.date()
                    ),
                    "test_end_date": str(
                        maximum_date.date()
                    ),
                    "number_of_series": int(
                        dataset[
                            SERIES_COLUMNS
                        ]
                        .drop_duplicates()
                        .shape[0]
                    ),
                    "dataset_rows": int(
                        len(dataset)
                    ),
                }
            )

            mlflow.log_metrics(metrics)

            dataset_summary = {
                "minimum_date": str(
                    dataset["sale_date"]
                    .min()
                    .date()
                ),
                "maximum_date": str(
                    maximum_date.date()
                ),
                "dataset_rows": int(
                    len(dataset)
                ),
                "evaluation_rows": int(
                    len(evaluation_data)
                ),
                "number_of_series": int(
                    dataset[
                        SERIES_COLUMNS
                    ]
                    .drop_duplicates()
                    .shape[0]
                ),
            }

            mlflow.log_dict(
                dataset_summary,
                "dataset_summary.json",
            )

            with TemporaryDirectory() as directory:
                artifact_directory = Path(directory)

                predictions_path = (
                    artifact_directory
                    / "predictions.csv"
                )

                plot_path = (
                    artifact_directory
                    / "aggregate_forecast.png"
                )

                columns_to_export = (
                    [
                        "sale_date",
                    ]
                    + SERIES_COLUMNS
                    + [
                        TARGET_COLUMN,
                        prediction_column,
                    ]
                )

                evaluation_data[
                    columns_to_export
                ].to_csv(
                    predictions_path,
                    index=False,
                )

                save_aggregate_plot(
                    predictions=evaluation_data,
                    prediction_column=prediction_column,
                    output_path=plot_path,
                )

                mlflow.log_artifact(
                    str(predictions_path),
                    artifact_path="predictions",
                )

                mlflow.log_artifact(
                    str(plot_path),
                    artifact_path="figures",
                )

        summary_rows.append(
            {
                "baseline": baseline_name,
                **metrics,
            }
        )

    summary = pd.DataFrame(
        summary_rows
    ).sort_values(
        "wape_percentage"
    )

    print()
    print("Baseline evaluation completed")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    run_baseline_experiments()