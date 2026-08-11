from __future__ import annotations

import os

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


def get_engine() -> Engine:
    validate_environment()

    database_url = URL.create(
        drivername="postgresql+psycopg",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=int(
            os.environ.get(
                "DB_PORT",
                "5432",
            )
        ),
        database=os.environ["DB_NAME"],
    )

    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )


def test_database_connection() -> dict:
    engine = get_engine()

    query = text(
        """
        SELECT
            current_database() AS database_name,
            current_user AS database_user
        """
    )

    with engine.connect() as connection:
        result = (
            connection
            .execute(query)
            .mappings()
            .one()
        )

    return dict(result)