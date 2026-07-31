FROM python:3.12.11-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

ARG PIP_VERSION=26.2
ARG SETUPTOOLS_VERSION=83.0.0

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y binutils gdal-bin libgdal-dev libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
RUN python -m pip install \
    "pip==${PIP_VERSION}" \
    "setuptools==${SETUPTOOLS_VERSION}"

FROM base AS development
RUN python -m pip install ".[dev]"

COPY . .
RUN chmod +x scripts/start-backend.sh

EXPOSE 8000
CMD ["/app/scripts/start-backend.sh"]

FROM base AS production
RUN python -m pip install .

COPY . .
RUN chmod +x scripts/start-backend.sh

EXPOSE 8000
CMD ["/app/scripts/start-backend.sh"]

