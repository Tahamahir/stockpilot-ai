from __future__ import annotations

import csv
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID

import pendulum
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk import dag, task


QUALITY_FILE = Path(
    "/opt/stockpilot/data/quality_samples/sales_invalid.csv"
)

POSTGRES_CONNECTION_ID = "stockpilot_postgres"

EXPECTED_COLUMNS = [
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
]


def is_valid_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def parse_decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None


def validate_row(
    row: dict[str, str],
    seen_references: set[str],
    valid_tenants: set[str],
    valid_store_pairs: set[tuple[str, str]],
    valid_product_pairs: set[tuple[str, str]],
) -> list[tuple[str, str]]:
    errors: list[tuple[str, str]] = []

    required_fields = [
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
    ]

    for field in required_fields:
        if not row.get(field, "").strip():
            errors.append(
                (
                    "missing_required_value",
                    f"Missing required value: {field}",
                )
            )

    sale_id = row.get("sale_id", "")
    tenant_id = row.get("tenant_id", "")
    store_id = row.get("store_id", "")
    product_id = row.get("product_id", "")
    sale_reference = row.get("sale_reference", "")

    if sale_id and not is_valid_uuid(sale_id):
        errors.append(
            ("invalid_uuid", "sale_id is not a valid UUID")
        )

    if tenant_id and not is_valid_uuid(tenant_id):
        errors.append(
            ("invalid_uuid", "tenant_id is not a valid UUID")
        )

    if store_id and not is_valid_uuid(store_id):
        errors.append(
            ("invalid_uuid", "store_id is not a valid UUID")
        )

    if product_id and not is_valid_uuid(product_id):
        errors.append(
            ("invalid_uuid", "product_id is not a valid UUID")
        )

    if tenant_id and tenant_id not in valid_tenants:
        errors.append(
            (
                "unknown_tenant",
                f"Unknown tenant_id: {tenant_id}",
            )
        )

    if (
        is_valid_uuid(tenant_id)
        and is_valid_uuid(store_id)
        and (tenant_id, store_id) not in valid_store_pairs
    ):
        errors.append(
            (
                "unknown_store",
                "The store does not belong to the tenant",
            )
        )

    if (
        is_valid_uuid(tenant_id)
        and is_valid_uuid(product_id)
        and (tenant_id, product_id) not in valid_product_pairs
    ):
        errors.append(
            (
                "unknown_product",
                "The product does not belong to the tenant",
            )
        )

    if sale_reference:
        if sale_reference in seen_references:
            errors.append(
                (
                    "duplicate_sale_reference",
                    f"Duplicate sale_reference: {sale_reference}",
                )
            )
        else:
            seen_references.add(sale_reference)

    sale_date_value = row.get("sale_date", "")

    if sale_date_value:
        try:
            date.fromisoformat(sale_date_value)
        except ValueError:
            errors.append(
                (
                    "invalid_date",
                    f"Invalid sale_date: {sale_date_value}",
                )
            )

    imported_at = row.get("imported_at", "")

    if imported_at:
        try:
            datetime.fromisoformat(imported_at)
        except ValueError:
            errors.append(
                (
                    "invalid_timestamp",
                    f"Invalid imported_at: {imported_at}",
                )
            )

    quantity: int | None = None

    try:
        quantity = int(row.get("quantity", ""))
        if quantity <= 0:
            errors.append(
                (
                    "invalid_quantity",
                    "quantity must be greater than zero",
                )
            )
    except ValueError:
        errors.append(
            (
                "invalid_quantity",
                "quantity must be an integer",
            )
        )

    unit_price = parse_decimal(row.get("unit_price", ""))

    if unit_price is None or unit_price < 0:
        errors.append(
            (
                "invalid_unit_price",
                "unit_price must be a positive number",
            )
        )

    discount = parse_decimal(
        row.get("discount_percentage", "")
    )

    if discount is None or discount < 0 or discount > 100:
        errors.append(
            (
                "invalid_discount",
                "discount_percentage must be between 0 and 100",
            )
        )

    total_amount = parse_decimal(
        row.get("total_amount", "")
    )

    if total_amount is None or total_amount < 0:
        errors.append(
            (
                "invalid_total_amount",
                "total_amount must be a positive number",
            )
        )

    if (
        quantity is not None
        and quantity > 0
        and unit_price is not None
        and discount is not None
        and total_amount is not None
    ):
        expected_total = (
            Decimal(quantity)
            * unit_price
            * (Decimal("1") - discount / Decimal("100"))
        ).quantize(Decimal("0.01"))

        if abs(expected_total - total_amount) > Decimal("0.01"):
            errors.append(
                (
                    "inconsistent_total_amount",
                    (
                        f"Expected total_amount={expected_total}, "
                        f"received={total_amount}"
                    ),
                )
            )

    return errors


@dag(
    dag_id="stockpilot_invalid_sales_quality_check",
    description=(
        "Validate intentionally invalid sales records and store "
        "the rejected rows in PostgreSQL."
    ),
    schedule=None,
    start_date=pendulum.datetime(2026, 8, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["stockpilot", "quality", "rejections"],
)
def stockpilot_invalid_sales_quality_check() -> None:

    @task
    def validate_file_structure() -> int:
        if not QUALITY_FILE.exists():
            raise FileNotFoundError(
                f"Quality sample not found: {QUALITY_FILE}"
            )

        with QUALITY_FILE.open(
            mode="r",
            encoding="utf-8",
            newline="",
        ) as file:
            reader = csv.reader(file)
            actual_columns = next(reader, None)
            row_count = sum(1 for _ in reader)

        if actual_columns != EXPECTED_COLUMNS:
            raise ValueError(
                f"Unexpected columns.\n"
                f"Expected: {EXPECTED_COLUMNS}\n"
                f"Actual: {actual_columns}"
            )

        if row_count == 0:
            raise ValueError(
                "The invalid quality sample contains no rows."
            )

        print(f"Quality sample contains {row_count} rows.")

        return row_count

    @task
    def validate_rows(
        expected_rows: int,
        dag_run_id: str,
    ) -> dict[str, Any]:
        hook = PostgresHook(
            postgres_conn_id=POSTGRES_CONNECTION_ID
        )

        tenant_rows = hook.get_records(
            "SELECT tenant_id::text FROM raw.companies;"
        )

        store_rows = hook.get_records(
            """
            SELECT tenant_id::text, store_id::text
            FROM raw.stores;
            """
        )

        product_rows = hook.get_records(
            """
            SELECT tenant_id::text, product_id::text
            FROM raw.products;
            """
        )

        valid_tenants = {row[0] for row in tenant_rows}
        valid_store_pairs = {
            (row[0], row[1]) for row in store_rows
        }
        valid_product_pairs = {
            (row[0], row[1]) for row in product_rows
        }

        seen_references: set[str] = set()
        valid_rows = 0
        rejected_rows = 0

        with QUALITY_FILE.open(
            mode="r",
            encoding="utf-8",
            newline="",
        ) as file:
            reader = csv.DictReader(file)

            for row_number, row in enumerate(
                reader,
                start=2,
            ):
                errors = validate_row(
                    row=row,
                    seen_references=seen_references,
                    valid_tenants=valid_tenants,
                    valid_store_pairs=valid_store_pairs,
                    valid_product_pairs=valid_product_pairs,
                )

                if not errors:
                    valid_rows += 1
                    continue

                rejected_rows += 1

                error_type = (
                    errors[0][0]
                    if len(errors) == 1
                    else "multiple_validation_errors"
                )

                error_message = " | ".join(
                    message
                    for _, message in errors
                )

                hook.run(
                    """
                    INSERT INTO raw.rejected_records (
                        source_file,
                        table_name,
                        row_number,
                        error_type,
                        error_message,
                        raw_record,
                        dag_run_id
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s::jsonb,
                        %s
                    );
                    """,
                    parameters=(
                        QUALITY_FILE.name,
                        "raw.sales",
                        row_number,
                        error_type,
                        error_message,
                        json.dumps(
                            row,
                            ensure_ascii=False,
                        ),
                        dag_run_id,
                    ),
                    autocommit=True,
                )

                print(
                    f"Rejected row {row_number}: "
                    f"{error_message}"
                )

        if valid_rows + rejected_rows != expected_rows:
            raise RuntimeError(
                "The processed row count does not match "
                "the expected row count."
            )

        return {
            "expected_rows": expected_rows,
            "valid_rows": valid_rows,
            "rejected_rows": rejected_rows,
            "dag_run_id": dag_run_id,
        }

    @task
    def verify_rejections(
        summary: dict[str, Any],
    ) -> None:
        hook = PostgresHook(
            postgres_conn_id=POSTGRES_CONNECTION_ID
        )

        result = hook.get_first(
            """
            SELECT COUNT(*)
            FROM raw.rejected_records
            WHERE dag_run_id = %s
              AND source_file = %s;
            """,
            parameters=(
                summary["dag_run_id"],
                QUALITY_FILE.name,
            ),
        )

        database_rejections = (
            int(result[0])
            if result
            else 0
        )

        if database_rejections != summary["rejected_rows"]:
            raise ValueError(
                "The number of PostgreSQL rejected records "
                "does not match the validation result."
            )

        if summary["rejected_rows"] != summary["expected_rows"]:
            raise ValueError(
                "This quality sample was expected to contain "
                "only invalid rows."
            )

        print("Quality validation completed successfully.")
        print(f"Expected rows: {summary['expected_rows']}")
        print(f"Valid rows: {summary['valid_rows']}")
        print(f"Rejected rows: {summary['rejected_rows']}")

    expected_rows = validate_file_structure()

    summary = validate_rows(
        expected_rows=expected_rows,
        dag_run_id="{{ run_id }}",
    )

    verify_rejections(summary)


stockpilot_invalid_sales_quality_check()