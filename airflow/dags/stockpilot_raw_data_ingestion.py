from __future__ import annotations
import shutil
import tempfile
import csv
from pathlib import Path
from typing import Any

import pendulum
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk import dag, task


DATA_DIRECTORY = Path("/opt/stockpilot/data/generated")
POSTGRES_CONNECTION_ID = "stockpilot_postgres"

TABLE_CONFIGS: list[dict[str, Any]] = [
    {
        "file_name": "companies.csv",
        "table_name": "companies",
        "columns": [
            "tenant_id",
            "company_name",
            "industry",
            "country",
            "created_at",
        ],
    },
    {
        "file_name": "stores.csv",
        "table_name": "stores",
        "columns": [
            "store_id",
            "tenant_id",
            "store_code",
            "store_name",
            "city",
            "region",
            "active",
            "created_at",
        ],
    },
    {
        "file_name": "suppliers.csv",
        "table_name": "suppliers",
        "columns": [
            "supplier_id",
            "tenant_id",
            "supplier_code",
            "supplier_name",
            "average_lead_time_days",
            "minimum_order_value",
            "active",
            "created_at",
        ],
    },
    {
        "file_name": "products.csv",
        "table_name": "products",
        "columns": [
            "product_id",
            "tenant_id",
            "supplier_id",
            "sku",
            "product_name",
            "category_name",
            "purchase_price",
            "selling_price",
            "lead_time_days",
            "minimum_order_quantity",
            "package_size",
            "active",
            "created_at",
        ],
    },
    {
        "file_name": "promotions.csv",
        "table_name": "promotions",
        "columns": [
            "promotion_id",
            "tenant_id",
            "product_id",
            "store_id",
            "start_date",
            "end_date",
            "discount_percentage",
        ],
    },
    {
        "file_name": "purchase_orders.csv",
        "table_name": "purchase_orders",
        "columns": [
            "purchase_order_id",
            "tenant_id",
            "supplier_id",
            "product_id",
            "store_id",
            "order_date",
            "expected_delivery_date",
            "actual_delivery_date",
            "ordered_quantity",
            "received_quantity",
            "status",
        ],
    },
    {
        "file_name": "sales.csv",
        "table_name": "sales",
        "columns": [
            "sale_id",
            "tenant_id",
            "sale_reference",
            "sale_date",
            "store_id",
            "product_id",
            "quantity",
            "unit_price",
            "discount_percentage",
            "total_amount",
            "imported_at",
        ],
    },
    {
        "file_name": "inventory.csv",
        "table_name": "inventory",
        "columns": [
            "inventory_id",
            "tenant_id",
            "inventory_date",
            "store_id",
            "product_id",
            "stock_on_hand",
            "quantity_on_order",
            "backorders",
            "imported_at",
        ],
    },
]


def count_csv_rows(file_path: Path) -> int:
    """Count data rows without loading the complete CSV into memory."""
    with file_path.open(
        mode="r",
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.reader(file)
        next(reader, None)
        return sum(1 for _ in reader)


@dag(
    dag_id="stockpilot_raw_data_ingestion",
    description=(
        "Validate and load the generated StockPilot CSV files "
        "into the PostgreSQL raw schema."
    ),
    schedule=None,
    start_date=pendulum.datetime(2026, 8, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["stockpilot", "ingestion", "postgresql"],
)
def stockpilot_raw_data_ingestion() -> None:

    @task
    def validate_csv_files() -> dict[str, int]:
        row_counts: dict[str, int] = {}

        for config in TABLE_CONFIGS:
            file_name = config["file_name"]
            expected_columns = config["columns"]
            file_path = DATA_DIRECTORY / file_name

            if not file_path.exists():
                raise FileNotFoundError(
                    f"Missing CSV file: {file_path}"
                )

            if file_path.stat().st_size == 0:
                raise ValueError(
                    f"CSV file is empty: {file_name}"
                )

            with file_path.open(
                mode="r",
                encoding="utf-8",
                newline="",
            ) as file:
                reader = csv.reader(file)
                actual_columns = next(reader, None)

            if actual_columns is None:
                raise ValueError(
                    f"CSV file has no header: {file_name}"
                )

            if actual_columns != expected_columns:
                raise ValueError(
                    f"Invalid columns in {file_name}.\n"
                    f"Expected: {expected_columns}\n"
                    f"Actual:   {actual_columns}"
                )

            row_count = count_csv_rows(file_path)

            if row_count == 0:
                raise ValueError(
                    f"CSV file contains no data: {file_name}"
                )

            row_counts[file_name] = row_count
            print(f"{file_name}: {row_count:,} rows validated")

        return row_counts

    @task
    def clear_existing_synthetic_data() -> None:
        hook = PostgresHook(
            postgres_conn_id=POSTGRES_CONNECTION_ID
        )

        hook.run(
            """
            TRUNCATE TABLE
                raw.inventory,
                raw.sales,
                raw.purchase_orders,
                raw.promotions,
                raw.products,
                raw.suppliers,
                raw.stores,
                raw.companies
            RESTART IDENTITY CASCADE;
            """,
            autocommit=True,
        )

        print("Existing synthetic business data removed.")

    @task
    def load_csv(
        config: dict[str, Any],
        dag_run_id: str,
    ) -> dict[str, Any]:
        file_name = config["file_name"]
        table_name = config["table_name"]
        columns = config["columns"]

        file_path = DATA_DIRECTORY / file_name
        detected_rows = count_csv_rows(file_path)

        hook = PostgresHook(
            postgres_conn_id=POSTGRES_CONNECTION_ID
        )

        hook.run(
            """
            INSERT INTO raw.ingestion_runs (
                dag_run_id,
                source_file,
                target_table,
                status,
                rows_detected
            )
            VALUES (%s, %s, %s, 'started', %s);
            """,
            parameters=(
                dag_run_id,
                file_name,
                f"raw.{table_name}",
                detected_rows,
            ),
            autocommit=True,
        )

        column_sql = ", ".join(columns)

        copy_sql = f"""
            COPY raw.{table_name} ({column_sql})
            FROM STDIN
            WITH (
                FORMAT CSV,
                HEADER TRUE,
                ENCODING 'UTF8'
            );
        """

        try:
         # PostgresHook with psycopg2 opens the file in r+ mode.
         # The source dataset is mounted read-only, so we create
         # a temporary writable copy inside the Airflow container.
            with tempfile.NamedTemporaryFile(
                prefix=f"stockpilot_{table_name}_",
                suffix=".csv",
                dir="/tmp",
                delete=False,
            ) as temporary_file:
                temporary_file_path = Path(temporary_file.name)
 
            shutil.copyfile(
                file_path,
                temporary_file_path,
            )

            hook.copy_expert(
                sql=copy_sql,
                filename=str(temporary_file_path),
            )

            loaded_result = hook.get_first(
                f"SELECT COUNT(*) FROM raw.{table_name};"
            )

            loaded_rows = (
                int(loaded_result[0])
                if loaded_result
                else 0
            )

            if loaded_rows != detected_rows:
                raise ValueError(
                    f"Row-count mismatch for {file_name}: "
                    f"CSV={detected_rows}, "
                    f"PostgreSQL={loaded_rows}"
                )

            hook.run(
                """
                UPDATE raw.ingestion_runs
                SET
                    status = 'success',
                    rows_loaded = %s,
                    finished_at = CURRENT_TIMESTAMP
                WHERE dag_run_id = %s
                  AND source_file = %s
                  AND target_table = %s
                  AND status = 'started';
                """,
                parameters=(
                    loaded_rows,
                    dag_run_id,
                    file_name,
                    f"raw.{table_name}",
                ),
                autocommit=True,
            )

            print(
                f"{file_name} loaded into raw.{table_name}: "
                f"{loaded_rows:,} rows"
            )

            return {
                "file_name": file_name,
                "table_name": table_name,
                "detected_rows": detected_rows,
                "loaded_rows": loaded_rows,
                "status": "success",
            }

        except Exception as error:
            hook.run(
                """
                UPDATE raw.ingestion_runs
                SET
                    status = 'failed',
                    error_message = %s,
                    finished_at = CURRENT_TIMESTAMP
                WHERE dag_run_id = %s
                  AND source_file = %s
                  AND target_table = %s
                  AND status = 'started';
                """,
                parameters=(
                    str(error),
                    dag_run_id,
                    file_name,
                    f"raw.{table_name}",
                ),
                autocommit=True,
            )

            raise

    @task
    def verify_ingestion(
        load_results: list[dict[str, Any]],
    ) -> None:
        failed_results = [
            result
            for result in load_results
            if result["status"] != "success"
        ]

        if failed_results:
            raise RuntimeError(
                f"Failed ingestion results: {failed_results}"
            )

        total_loaded = sum(
            result["loaded_rows"]
            for result in load_results
        )

        print("All StockPilot CSV files loaded successfully.")

        for result in load_results:
            print(
                f"raw.{result['table_name']}: "
                f"{result['loaded_rows']:,} rows"
            )

        print(f"Total loaded rows: {total_loaded:,}")

    validation = validate_csv_files()
    clear_data = clear_existing_synthetic_data()

    validation >> clear_data

    previous_task = clear_data
    load_tasks = []

    for config in TABLE_CONFIGS:
        table_name = config["table_name"]

        current_task = load_csv.override(
            task_id=f"load_{table_name}"
        )(
            config=config,
            dag_run_id="{{ run_id }}",
        )

        previous_task >> current_task
        previous_task = current_task
        load_tasks.append(current_task)

    verification = verify_ingestion(load_tasks)
    previous_task >> verification


stockpilot_raw_data_ingestion()