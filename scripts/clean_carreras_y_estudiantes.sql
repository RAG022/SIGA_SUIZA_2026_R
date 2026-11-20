-- ==============================================================================
-- SIGA Suiza 2026 - Script de Limpieza Controlada: Carreras y Estudiantes
-- ==============================================================================
-- Propósito:
--   Limpiar exclusivamente el catálogo de carreras, planes de estudio y todos
--   los registros de estudiantes (matrículas, notas, pagos, trámites) para
--   permitir la carga y pruebas limpias del sistema desde la interfaz.
--
-- Preserva intacto:
--   - Usuarios institucionales (core_users: admin@siga.edu, docente, tesoreria, etc.)
--   - Perfiles de personal (perfiles_personal: se desvinculan de programa temporalmente)
--   - Roles y Permisos (core_roles, core_permissions, core_user_roles, core_role_permissions)
--   - Módulos del sistema (core_modules)
--   - Periodos académicos (periodos_academicos: 2026-I, etc.)
--   - Catálogo de tasas TUPA y configuración de caja (tesoreria_conceptos, tesoreria_configuracion)
-- ==============================================================================

BEGIN;

-- 1. Desvincular programas de perfiles de personal
UPDATE perfiles_personal SET programa_estudio_id = NULL;

-- 2. Limpiar datos de estudiantes y sus registros académicos/financieros
TRUNCATE TABLE matricula_detalles CASCADE;
TRUNCATE TABLE evaluacion_registros CASCADE;
TRUNCATE TABLE matriculas CASCADE;
TRUNCATE TABLE historial_academico CASCADE;
TRUNCATE TABLE beneficios_estudiante CASCADE;
TRUNCATE TABLE registros_practicas CASCADE;
TRUNCATE TABLE solicitudes_tramites CASCADE;
TRUNCATE TABLE convalidaciones_detalle CASCADE;
TRUNCATE TABLE resoluciones_convalidacion CASCADE;
TRUNCATE TABLE tesoreria_pagos CASCADE;
TRUNCATE TABLE admision_postulantes CASCADE;
TRUNCATE TABLE estudiantes CASCADE;

-- 3. Limpiar mallas, unidades, módulos, planes y programas de estudio
TRUNCATE TABLE silabos CASCADE;
TRUNCATE TABLE carga_lectiva CASCADE;
TRUNCATE TABLE tutorias CASCADE;
TRUNCATE TABLE horarios_periodo CASCADE;
TRUNCATE TABLE planes_trabajo_docente CASCADE;
TRUNCATE TABLE programa_requisitos CASCADE;
TRUNCATE TABLE programa_configuraciones CASCADE;
TRUNCATE TABLE programa_unidades CASCADE;
TRUNCATE TABLE programa_modulos CASCADE;
TRUNCATE TABLE programas_estudio CASCADE;
TRUNCATE TABLE unidades_plan CASCADE;
TRUNCATE TABLE modulos_plan CASCADE;
TRUNCATE TABLE planes_estudio CASCADE;

-- 4. Limpiar cola de eventos outbox para evitar reprocesamiento de entidades eliminadas
TRUNCATE TABLE outbox_events;

-- 5. Eliminar tablas temporales de respaldo antiguo en BD
DROP TABLE IF EXISTS bak_estudiantes_programa_20261021;
DROP TABLE IF EXISTS bak_programas_plan_20261021;

COMMIT;
