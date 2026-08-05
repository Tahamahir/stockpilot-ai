from __future__ import annotations

from datetime import timedelta

import pendulum

from airflow.providers.standard.operators.trigger_dagrun import (
    TriggerDagRunOperator,
)
from airflow.sdk import DAG


with DAG(
    dag_id="stockpilot_end_to_end_pipeline",
    description=(
        "Execute the complete StockPilot pipeline from raw CSV ingestion "
        "to dbt analytics models and business tests."
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
        "retries": 0,
        "retry_delay": timedelta(minutes=1),
    },
    tags=[
        "stockpilot",
        "end-to-end",
        "airflow",
        "dbt",
        "analytics",
    ],
) as dag:

    # =====================================================
    # STEP 1: Load generated CSV files into PostgreSQL raw
    # =====================================================
    trigger_raw_data_ingestion = TriggerDagRunOperator(
        task_id="trigger_raw_data_ingestion",
        trigger_dag_id="stockpilot_raw_data_ingestion",
        wait_for_completion=True,
        poke_interval=10,
        fail_when_dag_is_paused=True,
        reset_dag_run=False,
        deferrable=False,
    )

    # =====================================================
    # STEP 2: Build dbt models and execute all tests
    # =====================================================
    trigger_dbt_transformations = TriggerDagRunOperator(
        task_id="trigger_dbt_transformations",
        trigger_dag_id="stockpilot_dbt_transformations",
        wait_for_completion=True,
        poke_interval=10,
        fail_when_dag_is_paused=True,
        reset_dag_run=False,
        deferrable=False,
    )

    # =====================================================
    # PIPELINE ORDER
    # =====================================================
    (
        trigger_raw_data_ingestion
        >> trigger_dbt_transformations
    )