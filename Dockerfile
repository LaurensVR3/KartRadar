FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Chromium for app/providers/sms_timing.py's periodic auth-token refresh —
# installed to a fixed path so it's reachable after we drop to a non-root user.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps chromium

COPY app/ ./app/
COPY catalog/ ./catalog/
COPY tracks.yaml catalog_overrides.json ./

RUN useradd --create-home appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app /ms-playwright
USER appuser

ENV DATA_DIR=/app/data
VOLUME ["/app/data"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
