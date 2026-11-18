# SIGA - Sistema Integrado de Gestión Académica

Este es el repositorio principal del Sistema Integrado de Gestión Académica (SIGA) para el Instituto de Educación Superior Tecnológico Público (IESTP).

Toda la documentación arquitectónica, técnica y de negocio oficial se encuentra centralizada en la carpeta `docs/`.

👉 **[Ver Documentación Principal (Índice Maestro)](docs/00-INDICE.md)**

Para conocer el estado actual y los siguientes pasos, revisa el [Informe de Estado](_estado.md).

## Levantar el proyecto con Docker

Requisitos: Docker Desktop corriendo y PostgreSQL local (puerto 5432) con la base `siga_suiza_2026`.

```powershell
# 1. Levantar todo el stack (Core, 7 módulos, frontend, NATS, Redis y pgAdmin)
docker compose up -d --build

# 2. Ver estado
docker compose ps
```

| Servicio | URL |
|----------|-----|
| Frontend (Vite) | http://localhost:5173 (también 3000 y 3001) |
| API / Gateway | http://localhost:8000 · Swagger: http://localhost:8000/docs |
| pgAdmin | http://localhost:5050 |
| NATS Monitoring | http://localhost:8222 |

**Credenciales**

- pgAdmin: `admin@siga.edu` / `admin123` (servidor "SIGA Suiza 2026 (Local)" ya registrado; al abrirlo pedirá una vez la contraseña de PostgreSQL: `admin123`).
- Aplicación: `admin@siga.edu` / `admin123` (superadmin). Otros roles: `tesoreria@`, `secretaria@`, `coordinador@`, `admision@`, `docente@`, `estudiante@`, `secretaria_prog@` (todos `@siga.edu`, misma contraseña).

La configuración de la base de datos vive en `.env` (`DB_HOST=host.docker.internal`, `DB_NAME=siga_suiza_2026`).

### Base de datos

El dump `dump_siga_suiza_2026_20261021.sql` se restaura en el PostgreSQL local:

```powershell
$env:PGPASSWORD='admin123'
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -U postgres -h localhost -c "CREATE DATABASE siga_suiza_2026 WITH TEMPLATE template0 ENCODING 'UTF8';"
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -U postgres -h localhost -d siga_suiza_2026 -f dump_siga_suiza_2026_20261021.sql
```

Para detener: `docker compose down`.

## Contribuir
Ver [CONTRIBUTING.md](CONTRIBUTING.md). Configuración local: copiar `siga_backend/.env.example` a `.env`.
