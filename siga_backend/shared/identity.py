"""
Módulo compartido de Identidad y Autorización para microservicios de SIGA.
Valida X-Internal-Token emitido por el Gateway y X-User-ID, extrayendo
roles y programa directamente de la base de datos sin acoplamiento a modelos ORM externos.
"""
from dataclasses import dataclass
from typing import List, Optional
import os
import logging
from jose import JWTError, jwt
from fastapi import HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("shared.identity")


@dataclass
class Identity:
    user_id: int
    roles: List[str]
    programa_id: Optional[int]
    is_superuser: bool


def _get_secret_key() -> str:
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    try:
        from app.core.config import settings
        if settings.secret_key:
            return settings.secret_key
    except Exception:
        pass
    return "change-me-in-production"


async def get_identity(request: Request, db: AsyncSession) -> Identity:
    """
    Verifica la identidad y el contexto de autorización de la solicitud:
    1. X-Internal-Token presente y válido (firma HS256, expiración, type='module_access').
    2. X-User-ID numérico.
    3. Usuario existente y activo en core_users.
    4. Roles y programa obtenidos directamente vía SQL.
    """
    # 1. Validar X-Internal-Token
    token = request.headers.get("X-Internal-Token") or request.headers.get("x-internal-token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado"
        )
    
    secret_key = _get_secret_key()
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado"
        )
    
    if payload.get("type") != "module_access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado"
        )

    # 2. Validar X-User-ID numérico
    raw_user_id = request.headers.get("X-User-ID") or request.headers.get("x-user-id")
    if not raw_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado"
        )
    try:
        user_id = int(raw_user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado"
        )

    # 3. Usuario existente y activo en core_users
    user_res = await db.execute(
        text("SELECT is_active, is_superuser FROM core_users WHERE id = :uid"),
        {"uid": user_id}
    )
    user_row = user_res.fetchone()
    if not user_row or not user_row[0]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado"
        )
    is_superuser = bool(user_row[1])

    # 4. Obtener roles (core_user_roles + core_roles) y programa (perfiles_personal)
    roles_res = await db.execute(
        text("""
            SELECT r.name 
            FROM core_user_roles ur 
            JOIN core_roles r ON ur.role_id = r.id 
            WHERE ur.user_id = :uid
        """),
        {"uid": user_id}
    )
    roles = [r[0].lower().strip() for r in roles_res.fetchall() if r[0]]

    perfil_res = await db.execute(
        text("SELECT programa_estudio_id FROM perfiles_personal WHERE user_id = :uid"),
        {"uid": user_id}
    )
    perfil_row = perfil_res.fetchone()
    programa_id = perfil_row[0] if perfil_row and perfil_row[0] is not None else None

    return Identity(
        user_id=user_id,
        roles=roles,
        programa_id=programa_id,
        is_superuser=is_superuser
    )


def es_superadmin(i: Identity) -> bool:
    """Verifica si el usuario es superadmin por flag de superusuario o por rol."""
    return i.is_superuser or "superadmin" in i.roles


def es_coordinador_de(i: Identity, programa_id: int) -> bool:
    """
    Verifica si el usuario es coordinador del programa académico indicado.
    Superadmin tiene acceso irrestricto.
    Un usuario con rol coordinador_programa sin programa asignado (None) NO califica.
    """
    if es_superadmin(i):
        return True
    if "coordinador_programa" in i.roles and i.programa_id is not None:
        return i.programa_id == programa_id
    return False


def es_docente_de_carga(i: Identity, carga_docente_id: Optional[int]) -> bool:
    """Verifica si el usuario es el docente asignado a la carga lectiva o es superadmin."""
    if es_superadmin(i):
        return True
    if carga_docente_id is not None and i.user_id == carga_docente_id:
        return True
    return False


async def es_coordinador_de_docente(i: Identity, docente_id: int, db: AsyncSession) -> bool:
    """
    Verifica si el usuario es coordinador y su programa coincide con el de al menos
    una carga lectiva asignada al docente_id.
    """
    if es_superadmin(i):
        return True
    if "coordinador_programa" not in i.roles or i.programa_id is None:
        return False
    res = await db.execute(
        text("SELECT 1 FROM carga_lectiva WHERE docente_id = :did AND programa_id = :pid LIMIT 1"),
        {"did": docente_id, "pid": i.programa_id}
    )
    return res.fetchone() is not None


ROLES_RESTRINGIDOS_POR_PROGRAMA = {
    "secretaria_academica",
    "secretaria_programa",
    "coordinador_programa",
}

ROLES_ACCESO_GLOBAL_ESTUDIANTES = {
    "superadmin",
    "admin",
    "director",
    "caja_tesoreria",
    "oficina_admision",
    "admin_admision",
}


def programa_autorizado_estudiantes(i: Identity) -> tuple[bool, Optional[int]]:
    """
    Determina si el usuario está restringido a una única carrera para consultar/gestionar estudiantes.

    Retorna (restringido, programa_id):
    - (False, None): acceso global (superadmin, admin, director, tesorería, admisión, etc.).
    - (True, int): restringido exclusivamente a su programa_estudio_id asignado.
    - (True, None): rol restringido por carrera sin programa asignado (fail-secure).
    """
    if es_superadmin(i) or any(r in ROLES_ACCESO_GLOBAL_ESTUDIANTES for r in i.roles):
        return False, None

    if any(r in ROLES_RESTRINGIDOS_POR_PROGRAMA for r in i.roles):
        return True, i.programa_id

    return False, None


def resolver_filtro_programa_estudiantes(
    i: Identity,
    programa_id_solicitado: Optional[int] = None,
) -> Optional[int]:
    """
    Resuelve el programa_id efectivo para listados/búsquedas de estudiantes.
    Si el usuario tiene rol restringido por carrera:
    - Sin carrera asignada -> HTTP 403 (fail-secure).
    - Solicitando una carrera distinta a la suya -> HTTP 403.
    - Sin parámetro o coincidente -> retorna su carrera asignada.
    """
    restringido, prog_asignado = programa_autorizado_estudiantes(i)
    if not restringido:
        return programa_id_solicitado

    if prog_asignado is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Su cuenta no tiene una carrera asignada para consultar estudiantes. Contacte al administrador.",
        )

    if programa_id_solicitado is not None and int(programa_id_solicitado) != int(prog_asignado):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para acceder a estudiantes de otra carrera.",
        )

    return prog_asignado


def verificar_acceso_estudiante(
    i: Identity,
    estudiante_programa_id: Optional[int],
) -> None:
    """
    Verifica que el usuario autenticado tenga permiso para acceder o modificar
    un estudiante concreto según su programa_id.
    """
    restringido, prog_asignado = programa_autorizado_estudiantes(i)
    if not restringido:
        return

    if prog_asignado is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Su cuenta no tiene una carrera asignada para acceder a este estudiante.",
        )

    if estudiante_programa_id is None or int(estudiante_programa_id) != int(prog_asignado):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para acceder a información de estudiantes de otra carrera.",
        )
