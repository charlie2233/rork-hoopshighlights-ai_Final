FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsm6 libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt

COPY app /app/services/inference/app
COPY training /app/services/inference/training
COPY datasets /app/services/inference/datasets
COPY models /app/services/inference/models
COPY evals /app/services/inference/evals

EXPOSE 8080

CMD ["uvicorn", "services.inference.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
