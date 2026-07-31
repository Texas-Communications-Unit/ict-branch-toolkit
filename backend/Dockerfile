FROM python:3.12.11-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y binutils gdal-bin libgdal-dev libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

FROM base AS development
ARG PIP_VERSION=26.2

COPY pyproject.toml ./
RUN python -m pip install "pip==${PIP_VERSION}"
RUN python -m pip install ".[dev]"

COPY . .
RUN chmod +x scripts/start-backend.sh

EXPOSE 8000
CMD ["/app/scripts/start-backend.sh"]

FROM base AS production-dependencies
ARG PIP_VERSION=26.2

COPY . .
RUN python -m pip install "pip==${PIP_VERSION}" \
    && python -m pip install --prefix=/opt/ict-runtime .

FROM base AS production
RUN rm -rf \
    /usr/local/bin/pip \
    /usr/local/bin/pip3 \
    /usr/local/bin/pip3.12 \
    /usr/local/lib/python3.12/site-packages/_distutils_hack \
    /usr/local/lib/python3.12/site-packages/distutils-precedence.pth \
    /usr/local/lib/python3.12/site-packages/pip \
    /usr/local/lib/python3.12/site-packages/pip-*.dist-info \
    /usr/local/lib/python3.12/site-packages/pkg_resources \
    /usr/local/lib/python3.12/site-packages/setuptools \
    /usr/local/lib/python3.12/site-packages/setuptools-*.dist-info

COPY --from=production-dependencies /opt/ict-runtime/ /usr/local/

COPY . .
RUN chmod +x scripts/start-backend.sh

EXPOSE 8000
CMD ["/app/scripts/start-backend.sh"]

