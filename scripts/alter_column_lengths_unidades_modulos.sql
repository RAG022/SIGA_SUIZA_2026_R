-- ==============================================================================
-- Migración: Ampliar longitud de columnas 'nombre' para planes y unidades MINEDU
-- ==============================================================================
-- Justificación:
--   Las unidades didácticas y módulos formativos según las mallas oficiales del MINEDU
--   (ej. Mecatrónica Automotriz, Enfermería Técnica) contienen descripciones de
--   capacidades técnicas y denominaciones que superan los 255 caracteres estándar,
--   provocando errores de truncamiento (StringDataRightTruncationError / HTTP 500).
-- ==============================================================================

BEGIN;

ALTER TABLE programa_unidades ALTER COLUMN nombre TYPE TEXT;
ALTER TABLE programa_modulos ALTER COLUMN nombre TYPE TEXT;
ALTER TABLE unidades_plan ALTER COLUMN nombre TYPE TEXT;
ALTER TABLE modulos_plan ALTER COLUMN nombre TYPE TEXT;
ALTER TABLE programas_estudio ALTER COLUMN nombre TYPE TEXT;
ALTER TABLE planes_estudio ALTER COLUMN nombre TYPE TEXT;

COMMIT;
