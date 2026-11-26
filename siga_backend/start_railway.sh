#!/bin/sh
set -e

echo "=========================================="
echo "🚀 Iniciando SIGA Backend (Railway)"
echo "=========================================="

PORT="${PORT:-8000}"
export PORT
echo "📡 Puerto principal: $PORT"

cleanup() {
    echo "🛑 Deteniendo servicios internos..."
    kill 0 2>/dev/null || true
    exit 0
}
trap cleanup EXIT INT TERM

if [ -n "$DATABASE_URL" ]; then
    echo "📦 DATABASE_URL detectada de Railway."
    export DB_URL="$DATABASE_URL"
fi

if [ "$SKIP_MIGRATIONS" != "true" ]; then
    echo "🔄 Ejecutando migraciones de base de datos..."
    alembic upgrade head || echo "⚠️ Alembic upgrade head falló o fue omitido — continuando..."
fi

export SIGA_MODULE_USUARIOS_URL="http://127.0.0.1:8001"
export SIGA_MODULE_PLANES_ESTUDIO_URL="http://127.0.0.1:8002"
export SIGA_MODULE_PROGRAMAS_ESTUDIO_URL="http://127.0.0.1:8005"
export SIGA_MODULE_GESTION_ACADEMICA_URL="http://127.0.0.1:8006"
export SIGA_MODULE_AUDITORIA_URL="http://127.0.0.1:8007"
export SIGA_MODULE_EVALUACION_URL="http://127.0.0.1:8008"
export SIGA_MODULE_ADMISION_URL="http://127.0.0.1:8009"

echo "⚙️ Levantando 7 microservicios internos (en secuencia)..."

# Cada módulo crea sus tablas al arrancar (create_all). Si arrancan a la vez chocan entre sí
# (duplicate key en pg_type) y se pierden tablas. Se arranca uno por uno y se espera su /health.
start_module() {
    name="$1"; port="$2"
    python -m uvicorn main:app --host 127.0.0.1 --port "$port" --app-dir "modules/$name" &
    i=0
    until curl -sf "http://127.0.0.1:$port/health" >/dev/null 2>&1; do
        i=$((i+1))
        if [ "$i" -ge 90 ]; then
            echo "⚠️ $name no respondió /health tras 90s — continuando..."
            break
        fi
        sleep 1
    done
    echo "✅ $name listo (puerto $port)"
}

start_module mod-usuarios 8001
start_module mod-planes-estudio 8002
start_module mod-programas-estudio 8005
start_module mod-gestion-academica 8006
start_module mod-auditoria 8007
start_module mod-evaluacion 8008
start_module mod-admision 8009

echo "🌐 Iniciando Core Gateway en 0.0.0.0:$PORT..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
