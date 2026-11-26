from fastapi import APIRouter, HTTPException, Depends, status, Request, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, text, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from database import get_db, OutboxEvent
from models import Estudiante, Matricula, MatriculaDetalle
from schemas import EstudianteCreate, EstudianteResponse, EstudianteUpdate, MatriculaCreate, MatriculaResponse, IngestaMasivaRequest
from datetime import datetime
from typing import List, Optional
from pathlib import Path
import uuid
from shared.identity import (
    es_solo_estudiante,
    get_identity,
    resolver_filtro_programa_estudiantes,
    verificar_acceso_estudiante,
)

router = APIRouter()


async def _obtener_estudiante_autorizado(
    request: Request,
    db: AsyncSession,
    estudiante_id: int,
    for_update: bool = False,
) -> Estudiante:
    """Carga el estudiante por ID y valida que pertenezca al ámbito de carrera del usuario autenticado."""
    ident = await get_identity(request, db)
    stmt = select(Estudiante).where(Estudiante.id == estudiante_id)
    if for_update:
        stmt = stmt.with_for_update()
    est = (await db.execute(stmt)).scalar_one_or_none()
    if not est:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    verificar_acceso_estudiante(ident, est.programa_id, est.id)
    return est

FOTO_DIR = Path(__file__).resolve().parent / "uploads" / "fotos"
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_FOTO_SIZE = 5 * 1024 * 1024  # 5 MB


async def _programas_validos(db: AsyncSession) -> set[int]:
    """IDs reales del catálogo de programas de estudios."""
    result = await db.execute(text("SELECT id FROM programas_estudio"))
    return set(result.scalars().all())


async def _codigos_usados(db: AsyncSession, year: int | None = None) -> set[str]:
    """Códigos de estudiante ya emitidos en el año indicado."""
    year = year or datetime.now().year
    result = await db.execute(
        select(Estudiante.codigo_estudiante).where(
            Estudiante.codigo_estudiante.like(f"{year}-%")
        )
    )
    return {str(c) for c in result.scalars().all()}


def _primer_codigo_libre(prefix: str, usados: set[str]) -> tuple[int, str]:
    """
    Primer sufijo de 6 dígitos no utilizado: AAAA-000001, AAAA-000002, ...

    Antes se calculaba max+1 sobre los sufijos de 6 dígitos, pero los códigos
    heredados son AAAA-DNI y algunos DNI históricos tienen 6 dígitos, así que
    el resultado arrancaba en valores como 2026-123740.
    """
    seq = 1
    while f"{prefix}{seq:06d}" in usados:
        seq += 1
    return seq, f"{prefix}{seq:06d}"


async def _siguiente_codigo_estudiante(db: AsyncSession) -> str:
    """Siguiente código secuencial libre del año (formato AAAA-000000)."""
    year = datetime.now().year
    prefix = f"{year}-"
    usados = await _codigos_usados(db, year)
    return _primer_codigo_libre(prefix, usados)[1]



def _foto_path_for(filename: str) -> Path:
    """Devuelve la ruta segura de un archivo de foto (previene path traversal)."""
    return FOTO_DIR / Path(filename).name


def _delete_foto(filename: str | None):
    """Elimina una foto del disco de forma best-effort."""
    if not filename:
        return
    file_name = Path(filename).name
    if not file_name:
        return
    try:
        _foto_path_for(file_name).unlink(missing_ok=True)
    except OSError:
        pass

@router.get("/fotos/{filename}")
async def obtener_foto(filename: str):
    """Sirve una foto de estudiante guardada en disco."""
    path = _foto_path_for(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    return FileResponse(path, media_type="image/jpeg")

@router.post("/estudiantes/{estudiante_id}/foto", response_model=EstudianteResponse)
async def subir_foto(estudiante_id: int, request: Request, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Sube o reemplaza la foto de un estudiante y guarda la URL en foto_url."""
    db_estudiante = await _obtener_estudiante_autorizado(request, db, estudiante_id)

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Formato de imagen inválido. Use JPG, PNG o WEBP")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    if len(content) > MAX_FOTO_SIZE:
        raise HTTPException(status_code=400, detail="La imagen supera los 5 MB")

    FOTO_DIR.mkdir(parents=True, exist_ok=True)
    ext = ALLOWED_IMAGE_TYPES[file.content_type]
    filename = f"{estudiante_id}_{uuid.uuid4().hex[:12]}{ext}"
    (FOTO_DIR / filename).write_bytes(content)

    if db_estudiante.foto_url:
        _delete_foto(db_estudiante.foto_url)
    db_estudiante.foto_url = f"/api/mod-gestion-academica/fotos/{filename}"

    event_payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "gestion_academica.estudiante.foto_actualizada",
        "source": "mod-gestion-academica",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "data": {"id": db_estudiante.id},
        "metadata": {"request_id": request.headers.get("X-Request-ID", "unknown")}
    }
    db.add(OutboxEvent(event_type=event_payload["event_type"], payload=event_payload))
    await db.commit()
    await db.refresh(db_estudiante)
    return db_estudiante

@router.delete("/estudiantes/{estudiante_id}/foto", response_model=EstudianteResponse)
async def eliminar_foto(estudiante_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """Elimina la foto de un estudiante (foto_url vuelve a null)."""
    db_estudiante = await _obtener_estudiante_autorizado(request, db, estudiante_id)

    if db_estudiante.foto_url:
        _delete_foto(db_estudiante.foto_url)
        db_estudiante.foto_url = None

    event_payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "gestion_academica.estudiante.foto_eliminada",
        "source": "mod-gestion-academica",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "data": {"id": db_estudiante.id},
        "metadata": {"request_id": request.headers.get("X-Request-ID", "unknown")}
    }
    db.add(OutboxEvent(event_type=event_payload["event_type"], payload=event_payload))
    await db.commit()
    await db.refresh(db_estudiante)
    return db_estudiante

@router.post("/admision/ingesta", status_code=status.HTTP_202_ACCEPTED)
async def ingesta_admitidos(request: Request, data: IngestaMasivaRequest, db: AsyncSession = Depends(get_db)):
    """
    Endpoint para ingestar de forma masiva (PUSH) los admitidos desde la App Externa de Admisión.
    Crea los expedientes de estudiantes y dispara eventos para integrarlos al ecosistema (crear usuarios, matricular, etc).
    """
    estudiantes_creados = 0
    omitidos = 0
    errores = 0

    # IDs reales de programas para no crear expedientes huérfanos
    programas_validos = await _programas_validos(db)

    # Secuencia de códigos coherente (AAAA-000000). Los códigos heredados
    # (AAAA-DNI) no participan, pero se evitan colisiones comprobando el set.
    year = datetime.now().year
    prefix = f"{year}-"
    usados = await _codigos_usados(db, year)
    secuencia, _ = _primer_codigo_libre(prefix, usados)

    # DNIs ya registrados, cargados una sola vez: antes se hacía un SELECT por
    # cada admitido (781 consultas y ~14 s para una resincronización completa).
    dnis_existentes = set((await db.execute(select(Estudiante.dni))).scalars().all())

    for admitido in data.admitidos:
        dni = (admitido.dni or "").strip()
        nombres = (admitido.nombres or "").strip()
        apellidos = (admitido.apellidos or "").strip()
        if not dni or not nombres or not apellidos or len(dni) > 15:
            omitidos += 1
            continue

        if dni in dnis_existentes:
            omitidos += 1
            continue

        programa_id = admitido.programa_id
        if programa_id not in programas_validos:
            programa_id = None

        try:
            # Savepoint por fila: un código/DNI duplicado ya no aborta el lote
            # completo con un 500.
            async with db.begin_nested():
                while f"{prefix}{secuencia:06d}" in usados:
                    secuencia += 1
                codigo = f"{prefix}{secuencia:06d}"
                usados.add(codigo)
                secuencia += 1

                db_estudiante = Estudiante(
                    codigo_estudiante=codigo,
                    dni=dni,
                    nombres=nombres,
                    apellidos=apellidos,
                    programa_id=programa_id,
                    celular=admitido.celular,
                    email_personal=admitido.email_personal,
                    modalidad_admision=admitido.modalidad or "ORDINARIO",
                    estado_academico="postulante",
                    metadata_admision=admitido.metadata_completa or {},
                )
                db.add(db_estudiante)
                await db.flush()  # para obtener el ID

                event_payload = {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "gestion_academica.admision.estudiante_ingresado",
                    "source": "mod-gestion-academica",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "version": "1.0.0",
                    "data": {
                        "estudiante_id": db_estudiante.id,
                        "dni": db_estudiante.dni,
                        "nombres": db_estudiante.nombres,
                        "apellidos": db_estudiante.apellidos,
                        "programa_id": programa_id,
                        "periodo_id": admitido.periodo_id,
                        "proceso_admision_id": data.proceso_admision_id,
                    },
                    "metadata": {"request_id": request.headers.get("X-Request-ID", "unknown")},
                }
                db.add(OutboxEvent(event_type=event_payload["event_type"], payload=event_payload))

            estudiantes_creados += 1
            dnis_existentes.add(dni)
        except IntegrityError:
            errores += 1
            continue

    await db.commit()
    return {
        "message": "Ingesta procesada",
        "estudiantes_creados": estudiantes_creados,
        "omitidos": omitidos,
        "errores": errores,
    }

@router.post("/estudiantes/", response_model=EstudianteResponse, status_code=status.HTTP_201_CREATED)
async def crear_estudiante(request: Request, data: EstudianteCreate, db: AsyncSession = Depends(get_db)):
    ident = await get_identity(request, db)
    programa_efectivo = resolver_filtro_programa_estudiantes(ident, data.programa_id)

    programas = await _programas_validos(db)
    if programa_efectivo is not None and programa_efectivo not in programas:
        raise HTTPException(
            status_code=400,
            detail="El programa de estudios seleccionado no existe en el catálogo.",
        )

    existing = await db.execute(select(Estudiante).where(
        or_(Estudiante.dni == data.dni, Estudiante.codigo_estudiante == data.codigo_estudiante)
    ))
    existing_student = existing.scalar_one_or_none()
    if existing_student:
        if existing_student.dni == data.dni:
            raise HTTPException(status_code=400, detail="El DNI ya se encuentra registrado en el sistema.")
        else:
            raise HTTPException(status_code=400, detail="El código de estudiante ya existe. Genere uno nuevo.")

    payload_dict = data.model_dump()
    payload_dict["programa_id"] = programa_efectivo
    db_estudiante = Estudiante(**payload_dict)
    db.add(db_estudiante)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="El DNI o el código de estudiante ya existe. Verifique los datos e intente nuevamente.",
        )
    
    event_payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "gestion_academica.estudiante.creado",
        "source": "mod-gestion-academica",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "data": {"id": db_estudiante.id, "dni": db_estudiante.dni, "nombre": f"{db_estudiante.nombres} {db_estudiante.apellidos}"},
        "metadata": {"request_id": request.headers.get("X-Request-ID", "unknown")}
    }
    
    db.add(OutboxEvent(event_type=event_payload["event_type"], payload=event_payload))
    await db.commit()
    await db.refresh(db_estudiante)
    return db_estudiante

@router.get("/estudiantes/")
async def obtener_estudiantes(
    request: Request,
    programa_id: Optional[int] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    ident = await get_identity(request, db)
    solo_estudiante = es_solo_estudiante(ident)
    programa_efectivo = None if solo_estudiante else resolver_filtro_programa_estudiantes(ident, programa_id)
    try:
        query = select(Estudiante).order_by(Estudiante.apellidos)
        if solo_estudiante:
            # El estudiante solo ve su propia ficha.
            query = query.where(Estudiante.id == (ident.estudiante_id or -1))
        if programa_efectivo is not None:
            query = query.where(Estudiante.programa_id == programa_efectivo)
        if search and search.strip():
            patron = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Estudiante.dni.ilike(patron),
                    Estudiante.nombres.ilike(patron),
                    Estudiante.apellidos.ilike(patron),
                    Estudiante.codigo_estudiante.ilike(patron),
                )
            )
        if skip > 0:
            query = query.offset(skip)
        if limit is not None and limit > 0:
            query = query.limit(limit)
        result = await db.execute(query)
        rows = result.scalars().all()
        # Payload de listado: se excluye metadata_admision (≈1,6 KB por fila)
        # y direccion_domicilio, que solo usa el detalle. Con 781 estudiantes
        # esto bajaba la respuesta de ~1,26 MB a ~150 KB.
        return [
            {
                "id": r.id,
                "codigo_estudiante": r.codigo_estudiante,
                "dni": r.dni,
                "nombres": r.nombres,
                "apellidos": r.apellidos,
                "estado_academico": r.estado_academico,
                "programa_id": r.programa_id,
                "foto_url": r.foto_url,
                "email_personal": r.email_personal,
                "email_institucional": r.email_institucional,
                "celular": r.celular,
                "fecha_nacimiento": r.fecha_nacimiento.isoformat() if r.fecha_nacimiento else None,
                "pago_matricula": r.pago_matricula,
                "documentos_completos": r.documentos_completos,
                "fecha_limite_documentos": r.fecha_limite_documentos.isoformat() if r.fecha_limite_documentos else None,
                "modalidad_admision": r.modalidad_admision,
            }
            for r in rows
        ]
    except Exception as e:
        import traceback
        print(f"[ERROR] obtener_estudiantes: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail="No se pudo obtener el listado de estudiantes. Intente nuevamente.",
        )

@router.get("/estudiantes/siguiente-codigo")
async def obtener_siguiente_codigo(db: AsyncSession = Depends(get_db)):
    """Devuelve el siguiente código de estudiante único del año actual (formato AAAA-000000)."""
    return {"codigo_estudiante": await _siguiente_codigo_estudiante(db)}

@router.get("/estudiantes/me", response_model=EstudianteResponse)
async def obtener_mi_ficha(request: Request, db: AsyncSession = Depends(get_db)):
    """Ficha del estudiante autenticado (vinculada por correo institucional)."""
    ident = await get_identity(request, db)
    if ident.estudiante_id is None:
        raise HTTPException(status_code=404, detail="Su usuario no está vinculado a una ficha de estudiante.")
    return await _obtener_estudiante_autorizado(request, db, ident.estudiante_id)

@router.put("/estudiantes/{estudiante_id}/pago_matricula", response_model=EstudianteResponse)
async def actualizar_pago_matricula(estudiante_id: int, request: Request, pagado: bool = True, db: AsyncSession = Depends(get_db)):
    estudiante = await _obtener_estudiante_autorizado(request, db, estudiante_id, for_update=True)

    if estudiante.pago_matricula == pagado:
        # Idempotente: el estado ya es el solicitado (reintento o doble envio).
        # No se modifica nada; el lock de fila se libera al cerrar la sesion.
        return estudiante

    estudiante.pago_matricula = pagado
    await db.commit()
    await db.refresh(estudiante)
    return estudiante

@router.get("/estudiantes/{estudiante_id}", response_model=EstudianteResponse)
async def obtener_estudiante(estudiante_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    return await _obtener_estudiante_autorizado(request, db, estudiante_id)

_ROMANOS = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII']

def _titulo_ciclo(numero):
    if numero is None:
        return 'CICLO'
    idx = int(numero) - 1
    return f"CICLO {_ROMANOS[idx]}" if 0 <= idx < len(_ROMANOS) else f"CICLO {numero}"

def _numero_ciclo(nombre_modulo, orden):
    import re
    if nombre_modulo:
        match = re.search(r'ciclo\s*(\d+)', str(nombre_modulo), re.IGNORECASE)
        if match:
            return int(match.group(1))
    return orden if orden is not None else 1

async def _construir_ciclos(db, estudiante_id, plan_id, periodo_id=None):
    """Documento historico: agrupa las unidades del plan por ciclo con la mejor nota del estudiante."""
    from sqlalchemy import text

    if not plan_id:
        return [], 0

    result_mod = await db.execute(
        text("SELECT id, nombre, orden FROM modulos_plan WHERE plan_id = :pid ORDER BY orden, id"),
        {"pid": plan_id}
    )
    modulos = result_mod.mappings().all()
    if not modulos:
        return [], 0

    modulo_ids = [m["id"] for m in modulos]
    placeholders = ','.join(f':m{i}' for i in range(len(modulo_ids)))
    result_uni = await db.execute(
        text(f"""
            SELECT id, modulo_id, nombre, codigo, creditos, horas, tipo, orden
            FROM unidades_plan
            WHERE modulo_id IN ({placeholders})
            ORDER BY modulo_id, orden, id
        """),
        {f'm{i}': mid for i, mid in enumerate(modulo_ids)}
    )
    unidades = result_uni.mappings().all()

    result_eval = await db.execute(
        text("""
            SELECT unidad_didactica_id, nota_c1, nota_c2, nota_c3, nota_final, estado, periodo_id
            FROM evaluacion_registros
            WHERE estudiante_id = :eid
              AND (nota_final IS NOT NULL OR nota_c1 IS NOT NULL OR nota_c2 IS NOT NULL OR nota_c3 IS NOT NULL)
        """),
        {"eid": estudiante_id}
    )
    evals = result_eval.mappings().all()

    result_per = await db.execute(text("SELECT id, codigo FROM periodos_academicos"))
    periodos = {p["id"]: p["codigo"] for p in result_per.mappings().all()}

    # Mejor registro por unidad: prioriza aprobado, luego nota mas alta, luego periodo mas reciente
    mejor = {}
    for e in evals:
        uid = e["unidad_didactica_id"]
        parciales = [n for n in (e["nota_c1"], e["nota_c2"], e["nota_c3"]) if n is not None]
        nota = e["nota_final"]
        if nota is None and parciales:
            nota = round(sum(parciales) / len(parciales))
        if nota is None:
            continue
        clave = (1 if e["estado"] == 'aprobado' else 0, nota, e["periodo_id"] or 0)
        actual = mejor.get(uid)
        if actual is None or clave > actual["_clave"]:
            mejor[uid] = {
                "nota": nota,
                "nota_c1": e["nota_c1"],
                "nota_c2": e["nota_c2"],
                "nota_c3": e["nota_c3"],
                "estado": e["estado"],
                "periodo_codigo": periodos.get(e["periodo_id"]),
                "_clave": clave,
            }

    # Docente por unidad (carga_lectiva): prefiere el periodo de la evaluacion, si no el vigente
    unidad_ids = [u["id"] for u in unidades]
    docentes_por_unidad = {}
    if unidad_ids:
        ph_ud = ','.join(f':u{i}' for i in range(len(unidad_ids)))
        result_cl = await db.execute(
            text(f"""
                SELECT cl.unidad_didactica_id, cl.periodo_id, cl.turno, cl.seccion, cu.full_name
                FROM carga_lectiva cl
                LEFT JOIN core_users cu ON cu.id = cl.docente_id
                WHERE cl.unidad_didactica_id IN ({ph_ud})
            """),
            {f'u{i}': uid for i, uid in enumerate(unidad_ids)}
        )
        for row in result_cl.mappings().all():
            uid = row["unidad_didactica_id"]
            opciones = docentes_por_unidad.setdefault(uid, [])
            opciones.append({
                "docente": row["full_name"],
                "turno": row["turno"],
                "seccion": row["seccion"],
                "periodo_id": row["periodo_id"],
            })

    unidades_por_modulo = {}
    for u in unidades:
        unidades_por_modulo.setdefault(u["modulo_id"], []).append(u)

    ciclos = {}
    for mod in modulos:
        num = _numero_ciclo(mod["nombre"], mod["orden"])
        ciclo = ciclos.setdefault(num, {"ciclo": num, "titulo": _titulo_ciclo(num), "unidades": []})
        for u in unidades_por_modulo.get(mod["id"], []):
            reg = mejor.get(u["id"])
            opciones = docentes_por_unidad.get(u["id"]) or []
            docente = None
            if opciones:
                periodo_eval = reg["_clave"][2] if reg else None
                docente = next((o for o in opciones if periodo_eval and o["periodo_id"] == periodo_eval), None)
                if docente is None and periodo_id:
                    docente = next((o for o in opciones if o["periodo_id"] == periodo_id), None)
                if docente is None:
                    docente = max(opciones, key=lambda o: o["periodo_id"] or 0)
            ciclo["unidades"].append({
                "nombre": u["nombre"],
                "codigo": u["codigo"],
                "creditos": u["creditos"],
                "horas": u["horas"],
                "tipo": u["tipo"],
                "nota": reg["nota"] if reg else None,
                "nota_c1": reg["nota_c1"] if reg else None,
                "nota_c2": reg["nota_c2"] if reg else None,
                "nota_c3": reg["nota_c3"] if reg else None,
                "estado": reg["estado"] if reg else "no_cursado",
                "periodo_codigo": reg["periodo_codigo"] if reg else None,
                "docente": docente["docente"] if docente else None,
                "turno": docente["turno"] if docente else None,
                "seccion": docente["seccion"] if docente else None,
            })

    salida = []
    for num in sorted(ciclos):
        c = ciclos[num]
        notas = [u["nota"] for u in c["unidades"] if u["nota"] is not None]
        c["promedio"] = round(sum(notas) / len(notas), 2) if notas else None
        c["creditos_ciclo"] = sum((u["creditos"] or 0) for u in c["unidades"])
        c["creditos_aprobados"] = sum((u["creditos"] or 0) for u in c["unidades"] if u["estado"] == 'aprobado')
        c["completado"] = len(c["unidades"]) > 0 and all(u["estado"] == 'aprobado' for u in c["unidades"])
        salida.append(c)

    return salida, len(salida)

async def _periodo_por_defecto_boletin(db, estudiante_id):
    """Periodo por defecto del boletin: ultima matricula del estudiante;
    si no tiene, el periodo vigente; si no, el mas reciente registrado."""
    from sqlalchemy import text

    result = await db.execute(
        text("""
            SELECT m.periodo_id
            FROM matriculas m
            JOIN periodos_academicos pa ON pa.id = m.periodo_id
            WHERE m.estudiante_id = :eid
            ORDER BY pa.fecha_inicio DESC NULLS LAST, m.id DESC
            LIMIT 1
        """),
        {"eid": estudiante_id},
    )
    periodo_id = result.scalars().first()
    if periodo_id:
        return periodo_id

    result = await db.execute(
        text("""
            SELECT id FROM periodos_academicos
            ORDER BY CASE estado WHEN 'en_curso' THEN 0 WHEN 'matricula_abierta' THEN 1 ELSE 2 END,
                     fecha_inicio DESC NULLS LAST, id DESC
            LIMIT 1
        """)
    )
    periodo_id = result.scalars().first()
    if periodo_id:
        return periodo_id

    raise HTTPException(status_code=404, detail="No hay periodos academicos registrados")

@router.get("/estudiantes/{estudiante_id}/boletin")
async def obtener_boletin(estudiante_id: int, request: Request, periodo_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text

    estudiante = await _obtener_estudiante_autorizado(request, db, estudiante_id)

    if periodo_id is None:
        periodo_id = await _periodo_por_defecto_boletin(db, estudiante_id)

    result_mat = await db.execute(
        select(Matricula).options(selectinload(Matricula.detalles))
        .where(Matricula.estudiante_id == estudiante_id)
        .where(Matricula.periodo_id == periodo_id)
    )
    matricula = result_mat.scalar_one_or_none()

    result_periodo = await db.execute(
        text("SELECT codigo, fecha_fin_matricula_regular, fecha_fin_matricula_extemporanea FROM periodos_academicos WHERE id = :pid"),
        {"pid": periodo_id}
    )
    periodo_row = result_periodo.mappings().first()
    periodo_codigo = periodo_row["codigo"] if periodo_row else "N/A"

    result_plan = await db.execute(
        text("""
            SELECT p.creditos_totales, p.nombre as plan_nombre, p.nivel_formativo, pr.plan_estudio_id
            FROM programas_estudio pr
            JOIN planes_estudio p ON pr.plan_estudio_id = p.id
            WHERE pr.id = :prog_id
        """),
        {"prog_id": estudiante.programa_id}
    )
    plan_row = result_plan.mappings().first()
    creditos_totales = plan_row["creditos_totales"] if plan_row else 0

    result_creditos_aprob = await db.execute(
        text("""
            SELECT COALESCE(SUM(md.creditos), 0) as total
            FROM matricula_detalles md
            JOIN matriculas m ON md.matricula_id = m.id
            WHERE m.estudiante_id = :eid
            AND md.estado_curso = 'aprobado'
        """),
        {"eid": estudiante_id}
    )
    creditos_aprobados = result_creditos_aprob.scalar()

    cursos_periodo = []
    if matricula and matricula.detalles:
        for det in matricula.detalles:
            result_unidad = await db.execute(
                text("SELECT nombre FROM unidades_plan WHERE id = :uid"),
                {"uid": det.unidad_didactica_id}
            )
            unidad_row = result_unidad.mappings().first()
            nombre_unidad = unidad_row["nombre"] if unidad_row else f"Unidad {det.unidad_didactica_id}"

            result_eval = await db.execute(
                text("""
                    SELECT nota_c1, nota_c2, nota_c3, nota_final, estado
                    FROM evaluacion_registros
                    WHERE matricula_detalle_id = :md_id
                """),
                {"md_id": det.id}
            )
            eval_row = result_eval.mappings().first()

            cursos_periodo.append({
                "unidad_nombre": nombre_unidad,
                "creditos": det.creditos,
                "nota_c1": eval_row["nota_c1"] if eval_row else None,
                "nota_c2": eval_row["nota_c2"] if eval_row else None,
                "nota_c3": eval_row["nota_c3"] if eval_row else None,
                "nota_final": eval_row["nota_final"] if eval_row else None,
                "estado": eval_row["estado"] if eval_row else det.estado_curso,
            })

    notas_finales = [c["nota_final"] for c in cursos_periodo if c["nota_final"] is not None]
    promedio_periodo = round(sum(notas_finales) / len(notas_finales)) if notas_finales else None
    aprobados = sum(1 for c in cursos_periodo if c["estado"] == "aprobado")
    desaprobados = sum(1 for c in cursos_periodo if c["estado"] == "desaprobado")

    result_hist = await db.execute(
        text("""
            SELECT DISTINCT m.periodo_id, pa.codigo as periodo_codigo
            FROM matriculas m
            JOIN periodos_academicos pa ON pa.id = m.periodo_id
            WHERE m.estudiante_id = :eid AND m.periodo_id != :current_pid
            ORDER BY pa.codigo
        """),
        {"eid": estudiante_id, "current_pid": periodo_id}
    )
    periodos_anteriores = result_hist.mappings().all()

    historial = []
    for p in periodos_anteriores:
        result_evals = await db.execute(
            text("""
                SELECT er.nota_final, er.estado
                FROM evaluacion_registros er
                WHERE er.estudiante_id = :eid AND er.periodo_id = :pid
            """),
            {"eid": estudiante_id, "pid": p["periodo_id"]}
        )
        evals = result_evals.mappings().all()
        notas_p = [e["nota_final"] for e in evals if e["nota_final"] is not None]
        hist_aprob = sum(1 for e in evals if e["estado"] == "aprobado")
        hist_desaprob = sum(1 for e in evals if e["estado"] == "desaprobado")
        historial.append({
            "periodo_codigo": p["periodo_codigo"],
            "promedio": round(sum(notas_p) / len(notas_p)) if notas_p else None,
            "cursos_aprobados": hist_aprob,
            "cursos_desaprobados": hist_desaprob,
        })

    result_observ = await db.execute(
        text("SELECT observaciones FROM matriculas WHERE estudiante_id = :eid AND periodo_id = :pid"),
        {"eid": estudiante_id, "pid": periodo_id}
    )
    observ_row = result_observ.mappings().first()
    observaciones = observ_row["observaciones"] if observ_row else None

    plan_estudio_id = plan_row["plan_estudio_id"] if plan_row else None
    ciclos, ciclos_totales = await _construir_ciclos(db, estudiante_id, plan_estudio_id, periodo_id)
    ciclos_completados = sum(1 for c in ciclos if c.get("completado"))

    return {
        "estudiante": {
            "foto_url": estudiante.foto_url,
            "nombres": estudiante.nombres,
            "apellidos": estudiante.apellidos,
            "codigo_estudiante": estudiante.codigo_estudiante,
            "dni": estudiante.dni,
            "celular": estudiante.celular,
            "email_personal": estudiante.email_personal,
            "programa_nombre": plan_row["plan_nombre"] if plan_row else None,
            "periodo_codigo": periodo_codigo,
            "fecha_emision": datetime.utcnow().strftime("%d/%m/%Y"),
        },
        "matricula_estado": {
            "pago_matricula": estudiante.pago_matricula,
            "tipo_ingreso": matricula.tipo_ingreso if matricula else None,
            "estado_matricula": matricula.estado_matricula if matricula else "sin_matricula",
            "fecha_fin_matricula_regular": str(periodo_row["fecha_fin_matricula_regular"]) if periodo_row and periodo_row["fecha_fin_matricula_regular"] else None,
            "fecha_fin_matricula_extemporanea": str(periodo_row["fecha_fin_matricula_extemporanea"]) if periodo_row and periodo_row["fecha_fin_matricula_extemporanea"] else None,
        },
        "estado_academico": estudiante.estado_academico,
        "progreso_creditos": {
            "creditos_aprobados": creditos_aprobados,
            "creditos_totales": creditos_totales,
            "porcentaje": round((creditos_aprobados / creditos_totales) * 100) if creditos_totales > 0 else 0,
        },
        "cursos_periodo": cursos_periodo,
        "ciclos": ciclos,
        "resumen": {
            "promedio_general": promedio_periodo,
            "cursos_aprobados": aprobados,
            "cursos_desaprobados": desaprobados,
            "total_cursos": len(cursos_periodo),
            "ciclos_completados": ciclos_completados,
            "ciclos_totales": ciclos_totales,
        },
        "historial": historial,
        "observaciones": observaciones,
    }

@router.put("/estudiantes/{estudiante_id}", response_model=EstudianteResponse)
async def actualizar_estudiante(estudiante_id: int, data: EstudianteUpdate, request: Request, db: AsyncSession = Depends(get_db)):
    ident = await get_identity(request, db)
    result = await db.execute(select(Estudiante).where(Estudiante.id == estudiante_id))
    db_estudiante = result.scalar_one_or_none()
    if not db_estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    verificar_acceso_estudiante(ident, db_estudiante.programa_id, db_estudiante.id)

    update_data = data.model_dump(exclude_unset=True)

    if "programa_id" in update_data and update_data["programa_id"] is not None:
        resolver_filtro_programa_estudiantes(ident, update_data["programa_id"])
        programas = await _programas_validos(db)
        if update_data["programa_id"] not in programas:
            raise HTTPException(
                status_code=400,
                detail="El programa de estudios seleccionado no existe en el catálogo.",
            )

    for key, value in update_data.items():
        setattr(db_estudiante, key, value)

    event_payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "gestion_academica.estudiante.actualizado",
        "source": "mod-gestion-academica",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "data": {"id": db_estudiante.id},
        "metadata": {"request_id": request.headers.get("X-Request-ID", "unknown")}
    }

    db.add(OutboxEvent(event_type=event_payload["event_type"], payload=event_payload))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="El DNI o el código de estudiante ya pertenece a otro expediente.",
        )
    await db.refresh(db_estudiante)
    return db_estudiante

@router.delete("/estudiantes/{estudiante_id}")
async def eliminar_estudiante(estudiante_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    db_estudiante = await _obtener_estudiante_autorizado(request, db, estudiante_id)

    foto = db_estudiante.foto_url

    # Las FKs de dependencias usan NO ACTION: se eliminan explícitamente antes
    # del expediente para no devolver un 500 de integridad referencial.
    await db.execute(
        text("DELETE FROM convalidaciones_detalle WHERE resolucion_id IN "
             "(SELECT id FROM resoluciones_convalidacion WHERE estudiante_id = :eid)"),
        {"eid": estudiante_id},
    )
    for tabla in (
        "tesoreria_pagos",
        "solicitudes_tramites",
        "registros_practicas",
        "resoluciones_convalidacion",
        "historial_academico",
        "beneficios_estudiante",
        "matriculas",
    ):
        await db.execute(
            text(f"DELETE FROM {tabla} WHERE estudiante_id = :eid"),
            {"eid": estudiante_id},
        )

    await db.delete(db_estudiante)

    event_payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "gestion_academica.estudiante.eliminado",
        "source": "mod-gestion-academica",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "data": {"id": estudiante_id},
        "metadata": {"request_id": request.headers.get("X-Request-ID", "unknown")}
    }

    db.add(OutboxEvent(event_type=event_payload["event_type"], payload=event_payload))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="El expediente tiene registros asociados que impiden su eliminación.",
        )

    if foto:
        _delete_foto(foto)

    return {"message": "Estudiante eliminado"}

@router.post("/matriculas/", response_model=MatriculaResponse, status_code=status.HTTP_201_CREATED)
async def realizar_matricula(request: Request, data: MatriculaCreate, db: AsyncSession = Depends(get_db)):
    ident = await get_identity(request, db)
    est = await _obtener_estudiante_autorizado(request, db, data.estudiante_id)
    programa_efectivo = resolver_filtro_programa_estudiantes(ident, data.programa_id or est.programa_id)

    # Validar si ya está matriculado en este periodo
    from sqlalchemy.future import select
    existing = await db.execute(
        select(Matricula).where(
            Matricula.estudiante_id == data.estudiante_id,
            Matricula.periodo_id == data.periodo_id,
            Matricula.estado_matricula.notin_(["anulado", "anulada"]),
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="El estudiante ya cuenta con una matrícula registrada para este periodo académico.")

    # Validar créditos
    total_creditos = sum(d.creditos for d in data.detalles)
    if total_creditos < 1 or total_creditos > 40:
        raise HTTPException(status_code=400, detail=f"La matrícula tiene {total_creditos} créditos. Debe estar entre 1 y 40 créditos")

    # Separar detalles
    matricula_data = data.model_dump(exclude={"detalles"})
    if programa_efectivo is not None:
        matricula_data["programa_id"] = programa_efectivo
    db_matricula = Matricula(**matricula_data)
    db.add(db_matricula)
    await db.flush() # Para obtener db_matricula.id

    for det in data.detalles:
        db_detalle = MatriculaDetalle(matricula_id=db_matricula.id, **det.model_dump())
        db.add(db_detalle)
    
    event_payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "gestion_academica.matricula.confirmada",
        "source": "mod-gestion-academica",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "data": {"matricula_id": db_matricula.id, "estudiante_id": db_matricula.estudiante_id, "creditos": total_creditos},
        "metadata": {"request_id": request.headers.get("X-Request-ID", "unknown")}
    }
    
    db.add(OutboxEvent(event_type=event_payload["event_type"], payload=event_payload))
    await db.commit()
    
    result = await db.execute(select(Matricula).options(selectinload(Matricula.detalles)).where(Matricula.id == db_matricula.id))
    return result.scalar_one()

@router.get("/matriculas/", response_model=List[MatriculaResponse])
async def obtener_matriculas(request: Request, programa_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    ident = await get_identity(request, db)
    programa_efectivo = resolver_filtro_programa_estudiantes(ident, programa_id)
    query = select(Matricula).options(selectinload(Matricula.detalles)).order_by(Matricula.created_at.desc())
    if programa_efectivo is not None:
        query = query.where(Matricula.programa_id == programa_efectivo)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/matriculas/estudiante/{estudiante_id}", response_model=List[MatriculaResponse])
async def obtener_matriculas_estudiante(estudiante_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    await _obtener_estudiante_autorizado(request, db, estudiante_id)
    result = await db.execute(select(Matricula).options(selectinload(Matricula.detalles)).where(Matricula.estudiante_id == estudiante_id).order_by(Matricula.created_at.desc()))
    return result.scalars().all()

@router.get("/matriculas/unidad/{unidad_id}/periodo/{periodo_id}")
async def obtener_estudiantes_por_unidad_endpoint(unidad_id: int, periodo_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """Nomina de una unidad: solo el docente asignado, personal de la carrera de la unidad o roles globales."""
    ident = await get_identity(request, db)
    if es_solo_estudiante(ident):
        raise HTTPException(status_code=403, detail="No tiene permisos para esta operación.")
    roles_globales = {"superadmin", "admin", "director", "secretaria_academica", "caja_tesoreria", "tesoreria", "oficina_admision", "admin_admision"}
    if not (ident.is_superuser or any(r in roles_globales for r in ident.roles)):
        es_docente = (await db.execute(
            text("SELECT 1 FROM carga_lectiva WHERE unidad_didactica_id = :u AND periodo_id = :p AND docente_id = :d LIMIT 1"),
            {"u": unidad_id, "p": periodo_id, "d": ident.user_id},
        )).fetchone()
        prog_unidad = (await db.execute(
            text("SELECT m.programa_id FROM programa_unidades u JOIN programa_modulos m ON u.programa_modulo_id = m.id WHERE u.id = :u"),
            {"u": unidad_id},
        )).scalar_one_or_none()
        misma_carrera = ident.programa_id is not None and prog_unidad is not None and int(ident.programa_id) == int(prog_unidad)
        if not (es_docente or misma_carrera):
            raise HTTPException(status_code=403, detail="No tiene permisos para ver la nómina de esta unidad.")
    return await obtener_estudiantes_por_unidad(unidad_id, periodo_id, db)

async def obtener_estudiantes_por_unidad(unidad_id: int, periodo_id: int, db: AsyncSession):
    query = (
        select(Estudiante, MatriculaDetalle.id.label("matricula_detalle_id"))
        .join(Matricula, Matricula.estudiante_id == Estudiante.id)
        .join(MatriculaDetalle, MatriculaDetalle.matricula_id == Matricula.id)
        .where(Matricula.periodo_id == periodo_id)
        .where(MatriculaDetalle.unidad_didactica_id == unidad_id)
        .where(Matricula.estado_matricula != "anulada")
    )
    result = await db.execute(query)
    rows = result.all()
    
    response = []
    for est, det_id in rows:
        est_dict = EstudianteResponse.model_validate(est).model_dump()
        est_dict["matricula_detalle_id"] = det_id
        response.append(est_dict)
        
    return response

@router.post("/matriculas/unidad/{unidad_id}/periodo/{periodo_id}/sincronizar")
async def sincronizar_estudiantes_seccion(unidad_id: int, periodo_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Sincroniza y matricula a los estudiantes activos del programa y ciclo que corresponda a esta unidad didáctica
    para que el docente disponga inmediatamente de la nómina completa en su registro de calificaciones.
    """
    query_ud = text("""
        SELECT u.id, u.creditos, m.programa_id, m.periodo as ciclo
        FROM programa_unidades u
        JOIN programa_modulos m ON u.programa_modulo_id = m.id
        WHERE u.id = :uid
    """)
    res_ud = await db.execute(query_ud, {"uid": unidad_id})
    row_ud = res_ud.fetchone()
    
    prog_id = row_ud[2] if row_ud else None
    creds = row_ud[1] if row_ud and row_ud[1] else 2
    ciclo = row_ud[3] if row_ud and row_ud[3] else 1
    
    # Buscar estudiantes que pertenezcan estrictamente al programa Y al ciclo de la unidad
    if prog_id:
        res_est = await db.execute(
            select(Estudiante)
            .where(Estudiante.programa_id == prog_id)
            .where(Estudiante.ciclo_actual == ciclo)
        )
        estudiantes = res_est.scalars().all()
    else:
        estudiantes = []
        
    if not estudiantes:
        return []
        
    for est in estudiantes:
        res_mat = await db.execute(
            select(Matricula).where(Matricula.estudiante_id == est.id).where(Matricula.periodo_id == periodo_id)
        )
        db_mat = res_mat.scalar_one_or_none()
        if not db_mat:
            db_mat = Matricula(
                estudiante_id=est.id,
                programa_id=prog_id or est.programa_id or 1,
                periodo_id=periodo_id,
                estado_matricula="confirmada",
                ciclo=ciclo,
                tipo_ingreso="regular",
                casuistica="regular"
            )
            db.add(db_mat)
            await db.flush()
            
        res_det = await db.execute(
            select(MatriculaDetalle)
            .where(MatriculaDetalle.matricula_id == db_mat.id)
            .where(MatriculaDetalle.unidad_didactica_id == unidad_id)
        )
        db_det = res_det.scalar_one_or_none()
        if not db_det:
            db_det = MatriculaDetalle(
                matricula_id=db_mat.id,
                unidad_didactica_id=unidad_id,
                estado_curso="cursando",
                creditos=creds
            )
            db.add(db_det)
            
    await db.commit()
    return await obtener_estudiantes_por_unidad(unidad_id, periodo_id, db)

@router.delete("/matriculas/{matricula_id}")
async def anular_matricula(matricula_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    ident = await get_identity(request, db)
    result = await db.execute(select(Matricula).where(Matricula.id == matricula_id))
    db_matricula = result.scalar_one_or_none()
    if not db_matricula:
        raise HTTPException(status_code=404, detail="Matrícula no encontrada")
    verificar_acceso_estudiante(ident, db_matricula.programa_id, db_matricula.estudiante_id)

    db_matricula.estado_matricula = "anulada"
    
    event_payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "gestion_academica.matricula.anulada",
        "source": "mod-gestion-academica",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "data": {"matricula_id": matricula_id, "estudiante_id": db_matricula.estudiante_id},
        "metadata": {"request_id": request.headers.get("X-Request-ID", "unknown")}
    }
    
    db.add(OutboxEvent(event_type=event_payload["event_type"], payload=event_payload))
    await db.commit()
    return {"message": "Matrícula anulada correctamente"}

# ================================
# FASE 4: TRAMITES Y CASUISTICAS
# ================================
from schemas import (
    SolicitudTramiteCreate, SolicitudTramiteResponse, 
    ResolucionConvalidacionCreate, ResolucionConvalidacionResponse,
    BeneficioEstudianteCreate, BeneficioEstudianteResponse
)
from models import SolicitudTramite, ResolucionConvalidacion, ConvalidacionDetalle, BeneficioEstudiante

ESTADOS_TRAMITE = {"pendiente", "en_proceso", "emitido", "rechazado", "aprobado"}

@router.post("/tramites/", response_model=SolicitudTramiteResponse, status_code=status.HTTP_201_CREATED)
async def crear_tramite(data: SolicitudTramiteCreate, request: Request, db: AsyncSession = Depends(get_db)):
    await _obtener_estudiante_autorizado(request, db, data.estudiante_id)
    db_tramite = SolicitudTramite(**data.model_dump())
    db.add(db_tramite)
    await db.commit()
    await db.refresh(db_tramite)
    return db_tramite

@router.get("/tramites/estudiante/{estudiante_id}", response_model=List[SolicitudTramiteResponse])
async def obtener_tramites_estudiante(estudiante_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    await _obtener_estudiante_autorizado(request, db, estudiante_id)
    result = await db.execute(
        select(SolicitudTramite)
        .where(SolicitudTramite.estudiante_id == estudiante_id)
        .order_by(SolicitudTramite.fecha_solicitud.desc())
    )
    return result.scalars().all()

@router.get("/tramites/", response_model=List[SolicitudTramiteResponse])
async def obtener_tramites(request: Request, db: AsyncSession = Depends(get_db)):
    ident = await get_identity(request, db)
    programa_efectivo = resolver_filtro_programa_estudiantes(ident, None)
    query = select(SolicitudTramite).order_by(SolicitudTramite.fecha_solicitud.desc())
    if programa_efectivo is not None:
        query = query.join(Estudiante, Estudiante.id == SolicitudTramite.estudiante_id).where(
            Estudiante.programa_id == programa_efectivo
        )
    result = await db.execute(query)
    return result.scalars().all()

@router.put("/tramites/{tramite_id}/estado", response_model=SolicitudTramiteResponse)
async def actualizar_estado_tramite(tramite_id: int, estado: str, request: Request, db: AsyncSession = Depends(get_db)):
    if estado not in ESTADOS_TRAMITE:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Use: {', '.join(sorted(ESTADOS_TRAMITE))}")
    result = await db.execute(select(SolicitudTramite).where(SolicitudTramite.id == tramite_id))
    db_tramite = result.scalar_one_or_none()
    if not db_tramite:
        raise HTTPException(status_code=404, detail="Trámite no encontrado")
    await _obtener_estudiante_autorizado(request, db, db_tramite.estudiante_id)
    
    db_tramite.estado = estado
    if estado in ["emitido", "rechazado", "aprobado"]:
        db_tramite.fecha_resolucion = datetime.utcnow().date()
        
    await db.commit()
    await db.refresh(db_tramite)
    return db_tramite

@router.post("/convalidaciones/", response_model=ResolucionConvalidacionResponse, status_code=status.HTTP_201_CREATED)
async def registrar_convalidacion(data: ResolucionConvalidacionCreate, request: Request, db: AsyncSession = Depends(get_db)):
    await _obtener_estudiante_autorizado(request, db, data.estudiante_id)
    existente = await db.execute(select(ResolucionConvalidacion).where(ResolucionConvalidacion.numero_resolucion == data.numero_resolucion))
    if existente.scalars().first():
        raise HTTPException(status_code=409, detail="Ya existe una resolución con ese número")
    if not data.detalles:
        raise HTTPException(status_code=400, detail="Debe indicar al menos una unidad convalidada")
    conval_data = data.model_dump(exclude={"detalles"})
    db_resolucion = ResolucionConvalidacion(**conval_data)
    db.add(db_resolucion)
    await db.flush() # para obtener el ID de la resolucion

    for det in data.detalles:
        db_detalle = ConvalidacionDetalle(resolucion_id=db_resolucion.id, **det.model_dump())
        db.add(db_detalle)

    await db.commit()
    # Refresh with relation
    result = await db.execute(select(ResolucionConvalidacion).options(selectinload(ResolucionConvalidacion.detalles)).where(ResolucionConvalidacion.id == db_resolucion.id))
    return result.scalar_one()

@router.get("/convalidaciones/", response_model=List[ResolucionConvalidacionResponse])
async def listar_convalidaciones(request: Request, db: AsyncSession = Depends(get_db)):
    ident = await get_identity(request, db)
    programa_efectivo = resolver_filtro_programa_estudiantes(ident, None)
    query = (
        select(ResolucionConvalidacion)
        .options(selectinload(ResolucionConvalidacion.detalles))
        .order_by(ResolucionConvalidacion.fecha_emision.desc(), ResolucionConvalidacion.id.desc())
    )
    if programa_efectivo is not None:
        query = query.join(Estudiante, Estudiante.id == ResolucionConvalidacion.estudiante_id).where(
            Estudiante.programa_id == programa_efectivo
        )
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/convalidaciones/estudiante/{estudiante_id}", response_model=List[ResolucionConvalidacionResponse])
async def obtener_convalidaciones_estudiante(estudiante_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    await _obtener_estudiante_autorizado(request, db, estudiante_id)
    result = await db.execute(select(ResolucionConvalidacion).options(selectinload(ResolucionConvalidacion.detalles)).where(ResolucionConvalidacion.estudiante_id == estudiante_id))
    return result.scalars().all()

@router.post("/beneficios/", response_model=BeneficioEstudianteResponse, status_code=status.HTTP_201_CREATED)
async def registrar_beneficio(data: BeneficioEstudianteCreate, request: Request, db: AsyncSession = Depends(get_db)):
    await _obtener_estudiante_autorizado(request, db, data.estudiante_id)
    if not 0 < data.porcentaje_descuento <= 100:
        raise HTTPException(status_code=400, detail="El porcentaje de descuento debe estar entre 0 y 100")
    db_beneficio = BeneficioEstudiante(**data.model_dump())
    db.add(db_beneficio)
    await db.commit()
    await db.refresh(db_beneficio)
    return db_beneficio

@router.get("/beneficios/", response_model=List[BeneficioEstudianteResponse])
async def listar_beneficios(request: Request, db: AsyncSession = Depends(get_db)):
    ident = await get_identity(request, db)
    programa_efectivo = resolver_filtro_programa_estudiantes(ident, None)
    query = select(BeneficioEstudiante).order_by(BeneficioEstudiante.id.desc())
    if programa_efectivo is not None:
        query = query.join(Estudiante, Estudiante.id == BeneficioEstudiante.estudiante_id).where(
            Estudiante.programa_id == programa_efectivo
        )
    result = await db.execute(query)
    return result.scalars().all()

@router.put("/beneficios/{beneficio_id}/desactivar", response_model=BeneficioEstudianteResponse)
async def desactivar_beneficio(beneficio_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BeneficioEstudiante).where(BeneficioEstudiante.id == beneficio_id))
    db_beneficio = result.scalar_one_or_none()
    if not db_beneficio:
        raise HTTPException(status_code=404, detail="Beneficio no encontrado")
    await _obtener_estudiante_autorizado(request, db, db_beneficio.estudiante_id)
    db_beneficio.activo = False
    await db.commit()
    await db.refresh(db_beneficio)
    return db_beneficio

@router.get("/beneficios/estudiante/{estudiante_id}", response_model=List[BeneficioEstudianteResponse])
async def obtener_beneficios_estudiante(estudiante_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    await _obtener_estudiante_autorizado(request, db, estudiante_id)
    result = await db.execute(select(BeneficioEstudiante).where(BeneficioEstudiante.estudiante_id == estudiante_id, BeneficioEstudiante.activo == True))
    return result.scalars().all()

