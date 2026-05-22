FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend ./backend
COPY scripts ./scripts
COPY frontend ./frontend

RUN mkdir -p /app/uploads /app/outputs

EXPOSE 6002

CMD ["gunicorn", "--bind", "0.0.0.0:6002", \
     "--workers", "1", "--threads", "4", \
     "--timeout", "3600", "--graceful-timeout", "60", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "backend.app:app"]
