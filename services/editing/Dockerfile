FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/srv/hoopclips/services/editing:/srv/hoopclips/ios/backend

WORKDIR /srv/hoopclips

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY services/editing/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY ios/backend/app ./ios/backend/app
COPY ios/HoopsClips/HoopsClips/Resources/Audio ./ios/HoopsClips/HoopsClips/Resources/Audio
COPY services/editing/editing_app ./services/editing/editing_app

EXPOSE 8080
CMD ["uvicorn", "editing_app.main:app", "--host", "0.0.0.0", "--port", "8080"]
