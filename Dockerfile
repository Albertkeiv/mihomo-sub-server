FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_CONFIG=/app/config.yaml

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mihomo_sub_server ./mihomo_sub_server

EXPOSE 8080

CMD ["uvicorn", "mihomo_sub_server.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]

