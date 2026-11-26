from fastapi import FastAPI
import os
import sys

_app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)
from routes import router
from database import init_db
import asyncio
from outbox_worker import outbox_worker

app = FastAPI(
    title="mod-usuarios",
    description="Módulo de gestión de usuarios, roles y permisos",
    version="1.0.0"
)

app.include_router(router)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "module": "mod-usuarios",
        "version": "1.0.0"
    }


@app.get("/manifest")
async def get_manifest():
    port = os.getenv("PORT", 8001)
    return {
        "name": "mod-usuarios",
        "version": "1.0.0",
        "api_version": "v1",
        "description": "Gestión de usuarios y roles",
        "endpoints": {"http": f"http://localhost:{port}"},
        "health_check": "/health"
    }


@app.on_event("startup")
async def startup():
    await init_db()
    asyncio.create_task(outbox_worker())
    print("Tablas creadas/verificadas")
    print("Modulo de Usuarios (RBAC) iniciado")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
