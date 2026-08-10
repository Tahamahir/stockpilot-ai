from __future__ import annotations

from datetime import timedelta

import pendulum

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG


ML_PROJECT_DIR = "/opt/stockpilot/ml/forecasting"
ML_PYTHON = "/opt/ml-venv/bin/python"


with DAG(
    dag_id="stockpilot_ml_forecasting_pipeline",

    description=(
        "Generate recursive demand forecasts and "
        "optimized replenishment recommendations."
    ),

    start_date=pendulum.datetime(
        2026,
        8,
        1,
        tz="UTC",
    ),

    schedule=None,
    catchup=False,
    max_active_runs=1,

    default_args={
        "owner": "stockpilot",
        "retries": 1,
        "retry_delay": timedelta(minutes=1),
    },

    tags=[
        "stockpilot",
        "ml",
        "forecasting",
        "inventory",
        "mlflow",
    ],

) as dag:

    # =====================================================
    # STEP 1 - Generate recursive 30-day forecasts
    # =====================================================

    generate_demand_forecast = BashOperator(
        task_id="generate_demand_forecast",

        cwd=ML_PROJECT_DIR,

        bash_command=(
            f"{ML_PYTHON} "
            "-m src.generate_recursive_forecast"
        ),

        env={
            "PYTHONPATH": ML_PROJECT_DIR,
        },

        append_env=True,
    )


    # =====================================================
    # STEP 2 - Generate replenishment recommendations
    # =====================================================

    generate_replenishment_recommendations = BashOperator(
        task_id="generate_replenishment_recommendations",

        cwd=ML_PROJECT_DIR,

        bash_command=(
            f"{ML_PYTHON} "
            "-m src.generate_replenishment_recommendations"
        ),

        env={
            "PYTHONPATH": ML_PROJECT_DIR,
        },

        append_env=True,
    )


    # =====================================================
    # PIPELINE
    # =====================================================

    (
        generate_demand_forecast
        >> generate_replenishment_recommendations
    )