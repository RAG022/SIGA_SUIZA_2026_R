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

## 4. Estado de los Siguientes Menús (Pendientes)

- [ ] **2. Gestión Académica Central** (Próximo a revisar)
- [ ] **3. Registro de Estudiantes**
- [ ] **4. Proceso de Matrícula**
- [ ] **5. Coordinación de Programa**
- [ ] **6. Panel Docente**
- [ ] **7. Supervisión de Actas**
- [ ] **8. Trámites y Casuísticas**
- [ ] **9. Boletín de Notas**
- [ ] **10. Finanzas y Pagos**
- [ ] **11. Administración**
