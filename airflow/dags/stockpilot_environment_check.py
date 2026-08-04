from __future__ import annotations

from pathlib import Path

import pendulum
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk import dag, task


GENERATED_DATA_DIRECTORY = Path("/opt/stockpilot/data/generated")

EXPECTED_FILES = [
    "companies.csv",
    "stores.csv",
    "suppliers.csv",
    "products.csv",
    "promotions.csv",
    "purchase_orders.csv",
    "sales.csv",
    "inventory.csv",
]

EXPECTED_SCHEMAS = {
    "raw",
    "staging",
    "intermediate",
    "analytics",
    "ml",
}


@dag(
    dag_id="stockpilot_environment_check",
    description=(
        "Validate the generated CSV files and the StockPilot "
        "PostgreSQL connection."
    ),
    schedule=None,
    start_date=pendulum.datetime(2026, 8, 1, tz="UTC"),
    catchup=False,
    tags=["stockpilot", "setup", "quality"],
)
def stockpilot_environment_check() -> None:
    @task
    def check_generated_files() -> dict[str, int]:
        if not GENERATED_DATA_DIRECTORY.exists():
            raise FileNotFoundError(
                f"Directory not found: {GENERATED_DATA_DIRECTORY}"
            )

        missing_files = [
            file_name
            for file_name in EXPECTED_FILES
            if not (
                GENERATED_DATA_DIRECTORY / file_name
            ).is_file()
        ]

        if missing_files:
            raise FileNotFoundError(
                "Missing generated files: "
                + ", ".join(missing_files)
            )

        file_sizes = {
            file_name: (
                GENERATED_DATA_DIRECTORY / file_name
            ).stat().st_size
            for file_name in EXPECTED_FILES
        }

        empty_files = [
            file_name
            for file_name, size in file_sizes.items()
            if size == 0
        ]

        if empty_files:
            raise ValueError(
                "Empty generated files: "
                + ", ".join(empty_files)
            )

        print("All expected CSV files are available.")

        for file_name, size in file_sizes.items():
            print(f"{file_name}: {size:,} bytes")

        return file_sizes

    @task
    def check_stockpilot_database() -> dict[str, object]:
        postgres_hook = PostgresHook(
            postgres_conn_id="stockpilot_postgres"
        )

        database_information = postgres_hook.get_first(
            """
            SELECT
                current_database(),
                current_user;
            """
        )

        if database_information is None:
            raise RuntimeError(
                "PostgreSQL did not return database information."
            )

        database_name, database_user = database_information

        schema_rows = postgres_hook.get_records(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name IN (
                'raw',
                'staging',
                'intermediate',
                'analytics',
                'ml'
            )
            ORDER BY schema_name;
            """
        )

        available_schemas = {
            row[0]
            for row in schema_rows
        }

        missing_schemas = (
            EXPECTED_SCHEMAS - available_schemas
        )

        if missing_schemas:
            raise ValueError(
                "Missing PostgreSQL schemas: "
                + ", ".join(sorted(missing_schemas))
            )

        table_count_result = postgres_hook.get_first(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'raw';
            """
        )

        raw_table_count = (
            int(table_count_result[0])
            if table_count_result
            else 0
        )

        print(f"Database: {database_name}")
        print(f"User: {database_user}")
        print(
            "Schemas: "
            + ", ".join(sorted(available_schemas))
        )
        print(f"Raw tables: {raw_table_count}")

        return {
            "database": database_name,
            "user": database_user,
            "schemas": sorted(available_schemas),
            "raw_table_count": raw_table_count,
        }

    files_check = check_generated_files()
    database_check = check_stockpilot_database()

    files_check >> database_check


stockpilot_environment_check()