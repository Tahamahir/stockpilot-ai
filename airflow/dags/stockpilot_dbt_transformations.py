from __future__ import annotations

from datetime import timedelta

import pendulum

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG


# =========================================================
# dbt configuration
# =========================================================
DBT_EXECUTABLE = "/opt/dbt-venv/bin/dbt"

# Projet dbt monté depuis Windows, de préférence en lecture seule.
DBT_SOURCE_DIR = "/opt/stockpilot/dbt"

# Copie temporaire accessible en écriture par l'utilisateur airflow.
DBT_RUNTIME_DIR = "/tmp/stockpilot-dbt"


def create_dbt_command(dbt_command: str) -> str:
    """
    Create a shell command that:
    1. Removes the previous temporary dbt project.
    2. Copies the source dbt project into /tmp.
    3. Removes old generated artifacts.
    4. Executes the requested dbt command.
    """

    return f"""
set -euo pipefail

echo "Preparing writable dbt runtime directory..."

rm -rf "{DBT_RUNTIME_DIR}"
mkdir -p "{DBT_RUNTIME_DIR}"

cp -R "{DBT_SOURCE_DIR}/." "{DBT_RUNTIME_DIR}/"

rm -rf \
    "{DBT_RUNTIME_DIR}/logs" \
    "{DBT_RUNTIME_DIR}/target"

mkdir -p \
    "{DBT_RUNTIME_DIR}/logs" \
    "{DBT_RUNTIME_DIR}/target"

echo "Running dbt command: {dbt_command}"

{DBT_EXECUTABLE} {dbt_command} \
    --project-dir "{DBT_RUNTIME_DIR}" \
    --profiles-dir "{DBT_RUNTIME_DIR}"
"""


# =========================================================
# DAG definition
# =========================================================
with DAG(
    dag_id="stockpilot_dbt_transformations",
    description=(
        "Build and test the StockPilot dbt transformation "
        "and analytics pipeline."
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
        "dbt",
        "postgresql",
        "analytics",
    ],
) as dag:

    # =====================================================
    # Task 1: Check dbt configuration and PostgreSQL access
    # =====================================================
    check_dbt_connection = BashOperator(
        task_id="check_dbt_connection",
        bash_command=create_dbt_command(
            "debug"
        ),
        cwd="/tmp",
    )

    # =====================================================
    # Task 2: Build models and run non-business tests
    # =====================================================
    run_dbt_build = BashOperator(
        task_id="run_dbt_build",
        bash_command=create_dbt_command(
            'build --exclude "test_type:singular"'
        ),
        cwd="/tmp",
    )

    # =====================================================
    # Task 3: Run singular business validation tests
    # =====================================================
    run_business_tests = BashOperator(
        task_id="run_business_tests",
        bash_command=create_dbt_command(
            'test --select "test_type:singular"'
        ),
        cwd="/tmp",
    )

    # =====================================================
    # Task dependencies
    # =====================================================
    (
        check_dbt_connection
        >> run_dbt_build
        >> run_business_tests
    )