FROM python:3.12-slim

WORKDIR /app

COPY assistant/requirements.txt /tmp/requirements.txt

RUN pip install \
    --no-cache-dir \
    --upgrade pip \
    && pip install \
        --no-cache-dir \
        -r /tmp/requirements.txt

COPY assistant/app /app/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]