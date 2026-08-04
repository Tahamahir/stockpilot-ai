FROM python:3.13-slim

WORKDIR /usr/app/dbt

# Install system dependencies required by dbt
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY dbt/requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir \
    -r /tmp/requirements.txt

ENTRYPOINT ["dbt"]