from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    mean_absolute_error,
    root_mean_squared_error,
)


def calculate_forecasting_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, float]:
    """Calculate global demand forecasting metrics."""

    actual = np.asarray(
        y_true,
        dtype=float,
    )

    predicted = np.asarray(
        y_pred,
        dtype=float,
    )

    predicted = np.clip(
        predicted,
        a_min=0,
        a_max=None,
    )

    absolute_error_sum = np.abs(
        actual - predicted
    ).sum()

    actual_sum = np.abs(actual).sum()

    wape = (
        absolute_error_sum / actual_sum * 100
        if actual_sum > 0
        else 0.0
    )

    return {
        "mae": float(
            mean_absolute_error(
                actual,
                predicted,
            )
        ),
        "rmse": float(
            root_mean_squared_error(
                actual,
                predicted,
            )
        ),
        "wape_percentage": float(wape),
        "mean_bias": float(
            np.mean(predicted - actual)
        ),
    }