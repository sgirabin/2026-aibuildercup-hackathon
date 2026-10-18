FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN addgroup --system app && adduser --system --ingroup app app
USER app

CMD exec gunicorn app.main:app --bind :${PORT} --workers 1 --threads 8 --timeout 120 --worker-class uvicorn.workers.UvicornWorker

