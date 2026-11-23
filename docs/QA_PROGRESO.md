# Plan de Aseguramiento de Calidad y Progreso de QA (SIGA)

> Documento de seguimiento continuo de verificación punta a punta, inventario, pruebas de integración y corrección de funcionalidades del SIGA (IESTP Suiza).

---

## 1. Estado General del Entorno y Servicios

- **Orquestación Docker:** 100% de contenedores levantados y operativos (`siga-core`, `siga-frontend`, 7 microservicios modulares, `nats`, `redis`, `pgadmin`).
- **Gateway Core:** Saludable (`/health` 200 OK, 7 módulos registrados y certificados en estándar 1.0).
- **Frontend Vite:** Activo en puerto `5173` (y `3000`), con proxy inverso hacia `siga-core:8000` en `/api`, `/auth`, `/core`, `/ws`.
- **Base de Datos:** PostgreSQL en local conectada (`siga_suiza_2026`).
- **Rama de Trabajo:** `mejoras/docente-coordinacion`.
- **Credenciales Sembradas de Prueba (`docs/90-CREDENCIALES-PRUEBA.md`):**
  * `admin@siga.edu` / `admin123` (Superadmin)
  * `secretaria@siga.edu` / `secretaria123` (Secretaría Central)
  * `secretaria_prog@siga.edu` / `secretariaprog123` (Secretaría de Programa)
  * `tesoreria@siga.edu` / `tesoreria123` (Caja y Tesorería)
  * `admision@siga.edu` / `admision123` (Oficina de Admisión)
  * `coordinador@siga.edu` / `coordinador123` (Coordinación de Programa)
  * `docente@siga.edu` / `docente123` (Docente)
  * `estudiante@siga.edu` / `estudiante123` (Estudiante)

---

## 2. Funcionalidades Globales (Header, Perfil, Seguridad y Sesión)

| Funcionalidad | Estado | Causa del problema | Archivos modificados | Cómo se verificó |
|---|---|---|---|---|
| **Cierre de Sesión** (`logout`) | ✅ OK | N/A (Operativo) | Ninguno | Invocación de `logout()` en menú dropdown: borra token de `localStorage`, desconecta WebSocket, reinicia contexto y redirige a `LoginForm`. |
| **Configurar / Cambiar Contraseña** (`ChangePasswordModal`) | ✅ OK | N/A (Operativo) | Ninguno | Modal accesible desde Navbar (botón directo y dropdown) y Sidebar (avatar y config). Valida contraseña actual, longitud mínima (6), coincidencia y diferencia con la anterior. Llama a `PUT /auth/change-password`. Verificado con ciclo completo (cambio temporal + revert) contra BD real vía API. |
| **Indicador WebSocket / Conexión en Tiempo Real** | ✅ OK | N/A (Operativo) | Ninguno | Conexión a `/ws` a través del proxy de Vite. Estado pulsante verde "En línea" cuando el WebSocket está activo. |
| **Asistente Virtual SIGA** (`SIGAAIAssistant`) | ✅ OK | N/A (Operativo) | Ninguno | Botón flotante accesible globalmente para soporte institucional. |

---

## 3. Menú 1: Dashboard General

**Rol principal con acceso en Sidebar:** `superadmin`, `admin`. (Los demás roles acceden a una vista adaptada si hacen clic en el logo superior).

| Funcionalidad | Estado | Causa del problema | Archivos modificados | Cómo se verificó |
|---|---|---|---|---|
| **Header de Bienvenida y Permisos** | ✅ OK | N/A (Operativo) | Ninguno | Muestra saludo con nombre completo (`user?.full_name`) y badge dinámico con el conteo de capacidades/permisos activos (`permissions.length`). |
| **Métricas Ejecutivas del Sistema** (Admin) | ✅ OK | N/A (Operativo) | Ninguno | Carga desde `GET /core/status` con token JWT: total de módulos (7), estado global (Saludable) y entorno (`development`, versión `1.0.0`). |
| **Ecosistema de Módulos Registrados** (Admin) | ✅ OK | N/A (Operativo) | Ninguno | Carga desde `GET /core/modules`: renderiza los 7 microservicios con sus nombres, versiones, descripciones y badges de estado (`healthy`). Muestra indicador verde de acceso según permisos del usuario. |
| **Accesos Rápidos: Gestión Académica y Actas** | ✅ OK | N/A (Operativo) | Ninguno | 3 glass-cards interactivas con hover 3D y flechas animadas: Coordinación de Programa, Panel Docente y Supervisión de Actas. Navegan directamente a sus vistas correspondientes (`onNavigate`). |
| **Vista Amigable para Roles No-Admin** | ✅ OK | N/A (Operativo) | Ninguno | Al ingresar un usuario no-admin mediante el logo superior, la vista oculta las métricas técnicas y presenta una tarjeta con ícono de cohete invitándolo a usar sus herramientas correspondientes. |
| **Restricción de Menú Lateral por Rol** | ✅ OK | N/A (Operativo) | Ninguno | Verificado en `DashboardLayout.jsx`: el ítem "Dashboard General" solo es renderizado en la barra de navegación para usuarios con roles `superadmin` o `admin`. |

---

## 4. Menú 2: Gestión Académica Central

**Rol principal con acceso en Sidebar:** `superadmin`, `admin`, `secretaria_academica`, `director`.

| Funcionalidad | Estado | Causa del problema | Archivos modificados | Cómo se verificó |
|---|---|---|---|---|
| **Subida e Importación de Planes MINEDU (Mismo Código de Carrera)** | ✅ OK | El backend rechazaba con 400 (`detail: Ya existe un programa...`) si la carrera con ese código o nombre ya existía en la base de datos, abortando la importación. | `siga_backend/modules/mod-programas-estudio/routes.py`, `siga_backend/modules/mod-planes-estudio/routes.py`, `siga_frontend/src/modules/academic/AcademicDashboard.jsx` | Modificado para actualización idempotente: sincroniza metadatos del programa, vincula nuevo plan y actualiza/agrega módulos y unidades sin duplicación. Verificado mediante API real con código existente `M2969-3-001`. |
| **Subida de Planes con Nombres Largos >255 chars (HTTP 500 en Mecatrónica)** | ✅ OK | `StringDataRightTruncationError`: la columna `nombre` en `programa_unidades`, `programa_modulos`, `unidades_plan`, `modulos_plan`, `programas_estudio` y `planes_estudio` era `VARCHAR(255)`, pero descripciones MINEDU (ej. Mecatrónica Automotriz, 280 chars) superaban el límite y abortaban a mitad del bucle de unidades. | `siga_backend/modules/mod-programas-estudio/models.py`, `siga_backend/modules/mod-programas-estudio/database.py`, `siga_backend/modules/mod-planes-estudio/models.py`, `siga_backend/modules/mod-planes-estudio/database.py`, `scripts/alter_column_lengths_unidades_modulos.sql` | Columnas migradas a `TEXT` en BD local, modelos actualizados a `Text` y auto-migración idempotente agregada en `init_db()` para entornos ya desplegados (Railway). Verificado con inserción transaccional de unidad de 280 caracteres. |
| **Editar Programa (`PUT /programas/{id}`)** | ✅ OK | `AcademicDashboard.jsx` pasaba `data: {...}` a `apiClient.request` (fetch ignora `data` y enviaba cuerpo vacío → 422). | `siga_frontend/src/modules/academic/AcademicDashboard.jsx` | Cambiado a `body: JSON.stringify(...)`. Probado vía API con `secretaria@siga.edu` → `200 OK` y `vite build` OK. |
| **Parametrización de Carrera (`POST /programas/{id}/configuracion`)** | ✅ OK | `AcademicDashboard.jsx` pasaba `data: {...}` a `apiClient.request` (fetch enviaba cuerpo vacío y guardaba solo defaults). | `siga_frontend/src/modules/academic/AcademicDashboard.jsx` | Cambiado a `body: JSON.stringify(...)`. Probado vía API con `secretaria@siga.edu` → `200 OK`. |
| **Filtro de Área Académica** | ✅ OK | Faltaba la opción `"Formación Técnica General"` (valor fallback de `getAreaByProgram`). | `siga_frontend/src/modules/academic/AcademicDashboard.jsx` | Agregada opción en el selector de áreas. |
| **Agregar Unidad Didáctica en Malla (`POST /modulos/{id}/unidades`)** | ✅ OK | `CurriculumMesh.jsx` pasaba `data: {...}` a `apiClient.request` (fetch enviaba cuerpo vacío → 422). | `siga_frontend/src/modules/academic/CurriculumMesh.jsx` | Cambiado a `body: JSON.stringify(...)`. Verificado `vite build` OK. |
| **Sidebar `secretaria_academica` — Registro de Estudiantes** | ✅ OK | `App.jsx` redirigía a `students` al iniciar sesión, pero `DashboardLayout.jsx` omitía `secretaria_academica` en el menú lateral. | `siga_frontend/src/layouts/DashboardLayout.jsx` | Agregado `'secretaria_academica'` al `NavItem` de Registro de Estudiantes. |
| **Edición de Estudiante (`EditStudentModal.jsx`)** | ✅ OK | Al guardar cambios, `meta` partía de `student.metadata_admision` (vacío en listado liviano) en vez del expediente completo cargado en `useEffect`, borrando datos socioeconómicos y de salud previos. | `siga_frontend/src/modules/students/EditStudentModal.jsx` | Preservado `fullMetadataRef.current` al cargar el expediente completo y fusionado al guardar. |
| **Aislamiento de Estudiantes por Carrera para Secretaría Académica (Backend + Frontend)** | ✅ OK | `mod-gestion-academica` no validaba `get_identity` ni `perfiles_personal.programa_estudio_id` en los endpoints de estudiantes, permitiendo ver/manipular estudiantes de otras carreras; además `StudentMaster.jsx` dejaba abierto el filtro de programas para `secretaria_academica`. | `siga_backend/shared/identity.py`, `siga_backend/modules/mod-gestion-academica/main.py`, `siga_backend/modules/mod-gestion-academica/routes.py`, `siga_backend/modules/mod-gestion-academica/matricula_routes.py`, `siga_frontend/src/modules/students/StudentMaster.jsx`, `siga_frontend/src/modules/students/EditStudentModal.jsx` | Implementado filtrado estricto y fail-secure en backend (`HTTP 403` ante intentos cruzados) + bloqueo de selector en frontend. Verificados los 8 escenarios: DSI (44/0), Administración (74/0), Contabilidad (79/0), Enfermería (258/0), 6 ataques API → `403`, búsqueda/paginación aisladas y `admin`/`tesoreria` con acceso global (781). |
| **Trámites y Casuísticas — Botones, Buscadores y Filtros** | ✅ OK | En `TramitesDashboard.jsx`, los botones "Nueva Solicitud Manual" y "Ver Detalles" no tenían `onClick`, y faltaban buscadores/filtros en Trámites, Convalidaciones y Becas. En `ConvalidacionesTab.jsx`, al cambiar de estudiante sin programa no se limpiaban `unidades`. | `siga_frontend/src/modules/academic/TramitesDashboard.jsx`, `siga_frontend/src/modules/academic/ConvalidacionesTab.jsx`, `siga_frontend/src/modules/academic/BecasTab.jsx` | Conectados modales de Nueva Solicitud (`POST /tramites/`) y Detalle, agregados buscadores y filtros por estado en las 3 pestañas, y limpiado de unidades en Convalidaciones. Verificado `vite build` y endpoints HTTP 200 con `secretaria@siga.edu`. |

---

## 5. Menú 4: Proceso de Matrícula

**Roles con acceso en Sidebar:** `superadmin`, `admin`, `secretaria_academica`, `secretaria_programa`, `coordinador_programa`.

| Funcionalidad | Estado | Causa del problema | Archivos modificados | Cómo se verificó |
|---|---|---|---|---|
| **Aislamiento por Rol y Carrera en Endpoints de Matrícula (Backend)** | ✅ OK | Los 13 endpoints de matrícula (`admision/upload-excel`, `admision/matricular-ingresantes`, `matriculas/propuesta`, `matriculas/restricciones`, `matriculas/tipos-alumnos`, `casuisticas/evaluar`, `matriculas/{id}/boleta`, `matriculas/boletas`, `matriculas/{id}/consolidar`, `matriculas/resultado`, `POST/GET/DELETE /matriculas/`) no validaban `get_identity` ni `perfiles_personal.programa_estudio_id`, exponiendo datos de otras carreras. Además `POST /matriculas/` verificaba `estado_matricula != 'anulado'` en vez de `notin_(['anulado', 'anulada'])`, impidiendo rematricular tras anulación. | `siga_backend/modules/mod-gestion-academica/matricula_routes.py`, `siga_backend/modules/mod-gestion-academica/routes.py` | Suite de 19 pruebas RBAC sobre BD real (`lisy@siga.edu` DSI 22, `gil@siga.edu` Coordinador DSI 22, `secretariadeenfermeria@siga.edu` Enfermería 25, 8 ataques cruzados → `403`) + pruebas vía Gateway (`admin@siga.edu` global 781; `secretaria_prog@siga.edu` sin carrera asignada → `403`). |
| **Dashboard de Matrícula y Paneles por Carrera (Frontend)** | ✅ OK | `EnrollmentDashboard.jsx` permitía cambiar el selector de carrera a `secretaria_academica`/`coordinador_programa` y disparaba fetch en cada tecla; `AdmissionPanel`, `DeterminacionPanel` y `RestriccionesPanel` preseleccionaban `programs[0]` (Mecatrónica) causando 403 en otras carreras; `TiposAlumnosPanel` mostraba IDs crudos (`Programa 22`); `EnrollmentProcess` dejaba `selection.program = null` al elegir estudiante en Paso 1; `ExtraordinaryEnrollmentModal` no sincronizaba `programa_id` al abrir; `EspecialesPanel` ocultaba errores 403 con `.catch(() => [])`. | `siga_frontend/src/modules/enrollment/EnrollmentDashboard.jsx`, `EnrollmentProcess.jsx`, `AdmissionPanel.jsx`, `DeterminacionPanel.jsx`, `RestriccionesPanel.jsx`, `TiposAlumnosPanel.jsx`, `ExtraordinaryEnrollmentModal.jsx`, `EspecialesPanel.jsx` | Bloqueo visual con badge de carrera para roles restringidos, resolución de `selection.program`, sincronización de modal, manejo de errores 403 y compilación `vite build` exitosa (0 errores). |

---

## 6. Estado de la Base de Datos

- **Respaldo Previo:** `backups/backup_siga_suiza_2026_20261120_174708.sql` (3.14 MB).
- **Script de Limpieza Selectiva:** `scripts/clean_carreras_y_estudiantes.sql`.
- **Estado Actual:**
  * `estudiantes`: 0 (Limpio)
  * `matriculas`: 0 (Limpio)
  * `programas_estudio`: 0 (Limpio)
  * `planes_estudio`: 0 (Limpio)
  * `core_users`: 13 (Preservados intactos para inicio de sesión en local, Railway y Vercel)
  * `core_roles` y `core_permissions`: Preservados intactos
  * `periodos_academicos`: Preservados intactos

---

## 7. Estado de los Siguientes Menús (Pendientes)

- [ ] **2. Gestión Académica Central** (Revisión completa de pestañas restantes: sedes, mallas, filtros)
- [x] **3. Registro de Estudiantes** (Aislamiento por carrera y edición verificados)
- [x] **4. Proceso de Matrícula** (Aislamiento por rol/carrera y paneles corregidos y verificados)
- [ ] **5. Coordinación de Programa**
- [ ] **6. Panel Docente**
- [ ] **7. Supervisión de Actas**
- [ ] **8. Trámites y Casuísticas**
- [ ] **9. Boletín de Notas**
- [ ] **10. Finanzas y Pagos**
- [ ] **11. Administración**
