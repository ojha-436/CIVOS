FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache google-cloud-bigquery google-genai \
    fastapi uvicorn python-multipart pillow pydantic pyyaml httpx typer rich \
    google-cloud-translate google-cloud-texttospeech google-cloud-speech \
    google-cloud-bigquery-connection

COPY . .

# The districts GeoJSON for point-in-polygon geo resolution
# api/geo.py reads it from console/public/data/districts.geojson (relative to repo root)

ENV HOST=0.0.0.0
ENV PORT=8080

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
