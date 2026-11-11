FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-app.txt .
RUN apk upgrade --no-cache \
    && pip install --no-cache-dir -r requirements-app.txt \
    && addgroup -g 10001 appuser \
    && adduser -D -u 10001 -G appuser appuser
COPY app ./app
COPY templates ./templates
COPY main.py .
COPY alembic.ini .
COPY migrations ./migrations
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port 8000"]
