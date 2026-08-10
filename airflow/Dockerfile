FROM apache/airflow:3.3.0


# =========================================================
# System dependencies
# =========================================================

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        python3-venv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


# =========================================================
# Isolated dbt virtual environment
# =========================================================

USER root

RUN rm -rf /opt/dbt-venv \
    && python -m venv /opt/dbt-venv \
    && chown -R airflow:root /opt/dbt-venv


COPY --chown=airflow:root \
    airflow/dbt-requirements.txt \
    /tmp/dbt-requirements.txt


USER airflow

RUN PIP_USER=false /opt/dbt-venv/bin/python -m pip install \
        --no-cache-dir \
        --upgrade pip \
    && PIP_USER=false /opt/dbt-venv/bin/python -m pip install \
        --no-cache-dir \
        -r /tmp/dbt-requirements.txt \
    && test -x /opt/dbt-venv/bin/dbt \
    && /opt/dbt-venv/bin/dbt --version


# =========================================================
# Isolated ML forecasting virtual environment
# =========================================================

USER root

RUN rm -rf /opt/ml-venv \
    && python -m venv /opt/ml-venv \
    && chown -R airflow:root /opt/ml-venv


COPY --chown=airflow:root \
    airflow/ml-requirements.txt \
    /tmp/ml-requirements.txt


USER airflow

RUN PIP_USER=false /opt/ml-venv/bin/python -m pip install \
        --no-cache-dir \
        --upgrade pip \
    && PIP_USER=false /opt/ml-venv/bin/python -m pip install \
        --no-cache-dir \
        -r /tmp/ml-requirements.txt \
    && /opt/ml-venv/bin/python -c \
        "import mlflow, sklearn, pandas, psycopg; print('ML environment OK')"


# =========================================================
# Airflow provider
# =========================================================

USER airflow

RUN pip install --no-cache-dir \
    "apache-airflow==${AIRFLOW_VERSION}" \
    apache-airflow-providers-postgres