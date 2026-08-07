from __future__ import annotations

import os
from functools import lru_cache

import pandas as pd
from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine


REQUIRED_ENVIRONMENT_VARIABLES = (
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
)


def validate_environment() -> None:
    """Validate the required PostgreSQL configuration."""

    missing_variables = [
        variable
        for variable in REQUIRED_ENVIRONMENT_VARIABLES
        if not os.getenv(variable)
    ]

    if missing_variables:
        raise RuntimeError(
            "Missing database environment variables: "
            + ", ".join(missing_variables)
        )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create and cache the PostgreSQL SQLAlchemy engine."""

    validate_environment()

    database_url = URL.create(
        drivername="postgresql+psycopg",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ["DB_NAME"],
    )

    return create_engine(
        database_url,
        pool_pre_ping=True,
    )


def load_daily_sales() -> pd.DataFrame:
    """Load daily product-store sales from the analytics schema."""

    query = text(
        """
        select
            sale_date::date as sale_date,
            tenant_id,
            store_id,
            product_id,
            sum(total_quantity_sold)::double precision
                as quantity_sold

        from analytics.fct_daily_sales

        group by
            sale_date,
            tenant_id,
            store_id,
            product_id

        order by
            tenant_id,
            store_id,
            product_id,
            sale_date
        """
    )

    engine = get_engine()

    with engine.connect() as connection:
        return pd.read_sql(query, connection)