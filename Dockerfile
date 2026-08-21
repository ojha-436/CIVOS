# Pinned by digest, not by tag. `python:3.12-slim` is a moving target: the same
# Dockerfile would build a different base next month, so a build that passed
# review is not the build that ships. Refresh deliberately, not silently:
#   docker buildx imagetools inspect python:3.12-slim
# This digest was resolved 21 Aug 2026 and verified against the Docker Hub
# registry API at the time it was written in.
FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS base

# Patch the base OS layer. A pinned digest fixes the userland versions too, so
# without this the image ships whatever CVEs the base had on the day it was cut.
RUN apt-get update && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies before source, so a code change does not reinstall the world.
#
# Installed from the committed lockfile, with hashes, and not from a hand-written
# package list. The previous form named ~12 packages inline, which meant:
#   - the image resolved whatever versions existed on build day, so a reviewed
#     build was not the shipped build;
#   - the list duplicated pyproject.toml and could drift from it silently;
#   - CI audited a different resolution than the one deployed.
#
# --require-hashes is the part that matters: it makes a substituted or
# republished artifact fail the build instead of installing quietly. It also
# forces the set to be fully pinned — uv export refuses to emit a partial one.
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.9.6 && \
    uv export --frozen --no-dev --no-emit-project \
        --format requirements-txt -o /tmp/requirements.txt && \
    uv pip install --system --no-cache --require-hashes -r /tmp/requirements.txt && \
    rm -f /tmp/requirements.txt

# .dockerignore keeps .env, the 5.9 GB launch film, and .git out of this. Verify
# with `docker build --no-cache --progress=plain .` and check the context size
# before changing it — the secrets in .env are live.
COPY . .

# Run unprivileged. Nothing here needs root: the process binds 8080 (not a
# privileged port), reads only files baked into the image, and writes nothing.
# Root in the container is one container-escape CVE away from root on the node.
RUN useradd --create-home --shell /usr/sbin/nologin --uid 10001 civos \
    && chown -R civos:civos /app
USER 10001

ENV HOST=0.0.0.0 \
    PORT=8080 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8080

# The districts GeoJSON for point-in-polygon geo resolution is read by
# api/geo.py from console/public/data/districts.geojson (relative to repo root).
#
# --proxy-headers: Cloud Run terminates TLS and forwards the caller in
# X-Forwarded-For, which api/guards.py rate-limits on. Without this uvicorn
# reports the load balancer as every client.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
