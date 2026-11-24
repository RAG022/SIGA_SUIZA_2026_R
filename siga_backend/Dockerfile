FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip -q && \
    pip install --no-cache-dir -r requirements.txt -q

FROM python:3.12-slim

WORKDIR /app

ARG BUILD_DATE
ARG VCS_REF

LABEL org.opencontainers.image.title="SIGA SUIZA Backend Core" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Production image: CPICE only required modules
COPY modules/mod-usuarios ./modules/mod-usuarios
COPY modules/mod-planes-estudio ./modules/mod-planes-estudio
COPY modules/mod-programas-estudio ./modules/mod-programas-estudio
COPY modules/mod-gestion-academica ./modules/mod-gestion-academica
COPY modules/mod-auditoria ./modules/mod-auditoria
COPY modules/mod-evaluacion ./modules/mod-evaluacion
COPY modules/mod-admision ./modules/mod-admision
COPY app ./app
COPY alembic ./alembic

RUN rm -rf tests

EXPOSE 8001 8002 8005 8006 8007 8008 8009

ENTRYPOINT ["sh", "./entrypoint.sh"]