FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# exiftool : vérifie que les rendus ne contiennent aucune métadonnée (tests, contrôle manuel).
# ffmpeg / ffprobe : métadonnées et rendus des vidéos et photos animées.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libimage-exiftool-perl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
