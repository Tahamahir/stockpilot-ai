from __future__ import annotations

import os

import streamlit as st
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
    """Verify that all required database variables are configured."""

    missing_variables = [
        variable
        for variable in REQUIRED_ENVIRONMENT_VARIABLES
        if not os.getenv(variable)
    ]

    if missing_variables:
        missing = ", ".join(missing_variables)

        raise RuntimeError(
            f"Missing required environment variables: {missing}"
        )


@st.cache_resource
def get_engine() -> Engine:
    """Create and cache the SQLAlchemy PostgreSQL engine."""

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
        pool_size=5,
        max_overflow=5,
    )


def test_database_connection() -> dict[str, str]:
    """Test PostgreSQL access and return connection information."""

    engine = get_engine()

    query = text(
        """
        select
            current_database() as database_name,
            current_user as database_user,
            current_schema() as current_schema
        """
    )

    with engine.connect() as connection:
        result = connection.execute(query).mappings().one()

    return dict(result)