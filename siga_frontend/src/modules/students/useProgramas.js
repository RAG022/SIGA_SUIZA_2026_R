import { useCallback, useEffect, useState } from 'react';
import { API_BASE } from '../../core/api/client';

export const SIN_PROGRAMA = 'Sin carrera asignada';

// Cache a nivel de modulo: StudentMaster, StudentDetail y EditStudentModal
// comparten una sola consulta del catalogo durante la sesion.
let cacheProgramas = null;
let cargaEnCurso = null;

function normalizarProgramas(data) {
  const lista = Array.isArray(data)
    ? data
    : (Array.isArray(data?.programas) ? data.programas : []);

  return lista
    .map((p) => ({
      id: String(p.id ?? ''),
      label: String(p.nombre ?? p.label ?? '').trim(),
    }))
    .filter((p) => p.id && p.label);
}

async function cargarCatalogo() {
  if (cacheProgramas) return cacheProgramas;
  if (cargaEnCurso) return cargaEnCurso;

  cargaEnCurso = (async () => {
    try {
      const res = await fetch(`${API_BASE}/api/mod-programas-estudio/programas`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      cacheProgramas = normalizarProgramas(data);
      return cacheProgramas;
    } finally {
      cargaEnCurso = null;
    }
  })();

  return cargaEnCurso;
}

/**
 * Carga el catalogo real de programas de estudios (mod-programas-estudio).
 * Evita los mapas hardcodeados que quedaban desincronizados con la BD.
 */
export function useProgramas() {
  const [programas, setProgramas] = useState(() => cacheProgramas || []);
  const [loading, setLoading] = useState(!cacheProgramas);

  useEffect(() => {
    // El estado inicial ya se tomó del caché de módulo cuando existe.
    if (cacheProgramas) return undefined;

    let activo = true;
    cargarCatalogo()
      .then((lista) => {
        if (activo) setProgramas(lista);
      })
      .catch((error) => {
        console.error('No se pudo cargar el catálogo de programas:', error);
      })
      .finally(() => {
        if (activo) setLoading(false);
      });

    return () => { activo = false; };
  }, []);

  const getProgramaLabel = useCallback((programaId) => {
    if (programaId === null || programaId === undefined || programaId === '') {
      return SIN_PROGRAMA;
    }
    if (loading && programas.length === 0) return 'Cargando carrera…';
    const encontrado = programas.find((p) => p.id === String(programaId));
    return encontrado ? encontrado.label : `Programa ${programaId}`;
  }, [programas, loading]);

  return { programas, loading, getProgramaLabel };
}

export default useProgramas;
