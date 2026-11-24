/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useMemo, useRef } from 'react';
import { useAuth } from '../../core/auth/useAuth';
import { apiClient } from '../../core/api/client';
import { useToast } from '../../core/ui/ToastContext';
import { GraduationCap, Calendar, ClipboardList, BookOpen, FileText, Upload, ExternalLink, CheckCircle2, RefreshCw, Lock, AlertTriangle } from 'lucide-react';

// Roles con acceso irrestricto al catálogo de programas. El resto (docente,
// coordinador de programa, secretarías) solo opera sobre su carrera asignada.
const ROLES_ACCESO_GLOBAL = new Set(['superadmin', 'admin', 'director']);

function normalizarRoles(user) {
  const roles = Array.isArray(user?.roles) ? user.roles : [];
  return roles
    .map((r) => (typeof r === 'string' ? r : r?.name || r?.nombre))
    .filter(Boolean)
    .map((r) => r.toLowerCase());
}

function useSafeToast() {
  try {
    return useToast();
  } catch {
    const noop = () => {};
    return {
      toast: { success: noop, error: noop, warning: noop, info: noop, dismiss: noop, clear: noop },
      success: noop,
      error: noop,
      warning: noop,
      info: noop,
      showSuccess: noop,
      showError: noop,
      showWarning: noop,
      showInfo: noop,
      dismiss: noop,
      clear: noop,
      toasts: [],
    };
  }
}

export function DocentePlanning() {
  const { user } = useAuth();
  const { toast } = useSafeToast();

  const [loading, setLoading] = useState(false);
  const [programs, setPrograms] = useState([]);
  const [periods, setPeriods] = useState([]);

  const [selectedProgram, setSelectedProgram] = useState('');
  const [selectedPeriod, setSelectedPeriod] = useState('');

  const [planActual, setPlanActual] = useState(null);

  const [cargaLectiva, setCargaLectiva] = useState([]);
  const [mallaFlat, setMallaFlat] = useState([]);
  const [silabos, setSilabos] = useState([]);
  const [_PLANES, setPlanes] = useState([]);

  const rolesUsuario = normalizarRoles(user);
  const rolPrincipal = String(user?.role || '').toLowerCase();
  const esAdminGlobal = Boolean(user?.is_superuser)
    || ROLES_ACCESO_GLOBAL.has(rolPrincipal)
    || rolesUsuario.some((r) => ROLES_ACCESO_GLOBAL.has(r));

  // Carrera asignada en la ficha del usuario (perfiles_personal.programa_estudio_id).
  const programaAsignado = !esAdminGlobal && user?.programa_id ? String(user.programa_id) : null;

  // Programas en los que el docente realmente tiene carga lectiva. Sirve de
  // respaldo cuando la cuenta no tiene una carrera registrada explícitamente.
  const programasCargaLectiva = useMemo(() => (
    [...new Set(cargaLectiva.map((c) => String(c.programa_id)).filter(Boolean))]
  ), [cargaLectiva]);

  const programasVisibles = useMemo(() => {
    if (esAdminGlobal) return programs;
    const permitidos = programaAsignado ? [programaAsignado] : programasCargaLectiva;
    if (permitidos.length === 0) return programs;
    const enCatalogo = programs.filter((p) => permitidos.includes(String(p.id)));
    const faltantes = permitidos
      .filter((id) => !programs.some((p) => String(p.id) === id))
      .map((id) => ({ id: Number(id), nombre: `Programa ${id}` }));
    return [...enCatalogo, ...faltantes];
  }, [esAdminGlobal, programaAsignado, programasCargaLectiva, programs]);

  const programaBloqueado = !esAdminGlobal && (Boolean(programaAsignado) || programasCargaLectiva.length > 0);
  const programaEfectivo = programaBloqueado
    ? (programaAsignado || programasCargaLectiva[0] || '')
    : selectedProgram;
  const nombrePrograma = programasVisibles.find((p) => String(p.id) === String(programaEfectivo))?.nombre
    || cargaLectiva.find((c) => String(c.programa_id) === String(programaEfectivo))?.programa_nombre
    || (programaEfectivo ? `Programa ${programaEfectivo}` : '');

  // Fetch initial data
  useEffect(() => {
    const fetchInitial = async () => {
      // Se calcula dentro del efecto para que la dependencia sea el id del
      // usuario y no la identidad del objeto (evita bucles de renderizado).
      const roles = normalizarRoles(user);
      const rol = String(user?.role || '').toLowerCase();
      const admin = Boolean(user?.is_superuser)
        || ROLES_ACCESO_GLOBAL.has(rol)
        || roles.some((r) => ROLES_ACCESO_GLOBAL.has(r));
      const asignado = !admin && user?.programa_id ? String(user.programa_id) : null;

      try {
        const [progRes, perRes, loadRes] = await Promise.all([
          apiClient.request('/api/mod-programas-estudio/programas').catch(() => []),
          apiClient.request('/api/mod-programas-estudio/periodos').catch(() => []),
          user?.id ? apiClient.request(`/api/mod-programas-estudio/docentes/${user.id}/carga-lectiva`).catch(() => []) : Promise.resolve([])
        ]);
        setPrograms(progRes || []);
        setPeriods(perRes || []);
        setCargaLectiva(loadRes || []);

        const programasConCarga = [...new Set((loadRes || []).map((c) => String(c.programa_id)).filter(Boolean))];

        let initProg = '';
        let initPer = '';
        if (asignado) {
          initProg = asignado;
        } else if (!admin && programasConCarga.length > 0) {
          initProg = programasConCarga[0];
        } else if (loadRes && loadRes.length > 0) {
          initProg = loadRes[0].programa_id.toString();
        }
        if (!initProg && progRes && progRes.length > 0) {
          initProg = progRes[0].id.toString();
        }
        if (loadRes && loadRes.length > 0 && loadRes[0].periodo_id) {
          initPer = loadRes[0].periodo_id.toString();
        }
        if (!initPer && perRes && perRes.length > 0) {
          const active = perRes.find(p => p.estado === 'matricula_abierta' || p.estado === 'abierto' || p.estado === 'ACTIVO');
          initPer = active ? active.id.toString() : perRes[perRes.length - 1].id.toString();
        }
        if (initProg) setSelectedProgram(initProg);
        if (initPer) setSelectedPeriod(initPer);
      } catch (e) {
        console.error('Error fetching initial data', e);
      }
    };
    if (user?.id) {
      fetchInitial();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  // Fetch malla when program changes (to get unidad names)
  useEffect(() => {
    if (!programaEfectivo) {
      setMallaFlat([]);
      return;
    }
    const fetchMalla = async () => {
      try {
        const res = await apiClient.request(`/api/mod-programas-estudio/programas/${programaEfectivo}/malla`);
        const flat = [];
        (res || []).forEach(modulo => {
          (modulo.unidades || []).forEach(ud => {
            flat.push({ ...ud, modulo_nombre: modulo.nombre, periodo_sugerido: modulo.periodo });
          });
        });
        setMallaFlat(flat);
      } catch (e) {
        console.error('Error fetching malla', e);
      }
    };
    fetchMalla();
  }, [programaEfectivo]);

  // Fetch Silabos and Planes when Period changes
  useEffect(() => {
    if (!programaEfectivo || !selectedPeriod || !user?.id) return;

    const fetchData = async () => {
      setLoading(true);
      try {
        // Planes
        const planesRes = await apiClient.request(`/api/mod-programas-estudio/docente/${user.id}/planes-trabajo?periodo_id=${selectedPeriod}`).catch(() => []);
        // Silabos
        const silabosRes = await apiClient.request(`/api/mod-programas-estudio/docente/${user.id}/silabos`).catch(() => []);

        setPlanes(planesRes || []);
        const plan = (planesRes || []).find(p => String(p.programa_id) === String(programaEfectivo))
          || (planesRes || []).find(p => p.programa_id == null)
          || null;
        setPlanActual(plan);
        setSilabos(silabosRes || []);
      } catch (e) {
        console.error('Error fetching planning data', e);
      }
      setLoading(false);
    };
    fetchData();
  }, [programaEfectivo, selectedPeriod, user?.id]);

  const fileInputRefSilabo = useRef(null);
  const fileInputRefPlan = useRef(null);
  const uploadingTargetRef = useRef(null);
  const [uploadingTarget, setUploadingTarget] = useState(null); // { type: 'silabo' | 'plan', id?: number }

  const triggerUploadSilabo = (cargaId) => {
    const target = { type: 'silabo', id: cargaId };
    uploadingTargetRef.current = target;
    setUploadingTarget(target);
    if (fileInputRefSilabo.current) fileInputRefSilabo.current.click();
  };

  const handleUploadSilabo = async (e) => {
    const file = e.target.files && e.target.files[0];
    const target = uploadingTargetRef.current || uploadingTarget;
    if (!file) {
      uploadingTargetRef.current = null;
      setUploadingTarget(null);
      return;
    }
    if (!target || target.type !== 'silabo') return;
    if (!user?.id) {
      toast.error("No se pudo identificar la sesión del docente.");
      return;
    }

    // Simular subida (en producción se subiría a S3/GCS y se obtendría la URL)
    const simulatedUrl = `/docs/silabos/${file.name.replace(/\s+/g, '_')}`;
    const cargaId = target.id;

    try {
      const payload = {
        carga_lectiva_id: parseInt(cargaId, 10),
        estado: "presentado",
        archivo_url: simulatedUrl
      };
      await apiClient.request('/api/mod-programas-estudio/silabos', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      toast.success("Sílabo enviado correctamente al Coordinador");

      // Refresh silabos con tolerancia a fallos
      const silabosRes = await apiClient.request(`/api/mod-programas-estudio/docente/${user.id}/silabos`).catch(() => []);
      if (silabosRes) {
        setSilabos(silabosRes);
      }
    } catch (err) {
      toast.error(err.message || "Error al enviar el sílabo");
    } finally {
      e.target.value = ''; // reset input
      uploadingTargetRef.current = null;
      setUploadingTarget(null);
    }
  };

  const triggerUploadPlan = () => {
    if (!selectedPeriod || !programaEfectivo) {
      toast.warning("Por favor seleccione un programa y periodo académico antes de enviar el Plan de Trabajo.");
      return;
    }
    const target = { type: 'plan' };
    uploadingTargetRef.current = target;
    setUploadingTarget(target);
    if (fileInputRefPlan.current) fileInputRefPlan.current.click();
  };

  const handleUploadPlan = async (e) => {
    const file = e.target.files && e.target.files[0];
    const target = uploadingTargetRef.current || uploadingTarget;
    if (!file) {
      uploadingTargetRef.current = null;
      setUploadingTarget(null);
      return;
    }
    if (!target || target.type !== 'plan') return;

    if (!selectedPeriod || !programaEfectivo) {
      toast.warning("Por favor seleccione un programa y periodo académico antes de enviar el Plan de Trabajo.");
      return;
    }
    if (!user?.id) {
      toast.error("No se pudo identificar la sesión del docente.");
      return;
    }

    // Simular subida
    const simulatedUrl = `/docs/planes/${file.name.replace(/\s+/g, '_')}`;

    try {
      const payload = {
        periodo_id: parseInt(selectedPeriod, 10),
        programa_id: parseInt(programaEfectivo, 10),
        docente_id: parseInt(user.id, 10),
        estado: "presentado",
        archivo_url: simulatedUrl
      };
      await apiClient.request('/api/mod-programas-estudio/planes-trabajo', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      toast.success("Plan de Trabajo enviado correctamente al Coordinador");

      // Refresh planes con tolerancia a fallos
      const planesRes = await apiClient.request(`/api/mod-programas-estudio/docente/${user.id}/planes-trabajo?periodo_id=${selectedPeriod}`).catch(() => []);
      if (planesRes) {
        setPlanes(planesRes);
        const plan = planesRes.find(p => String(p.programa_id) === String(programaEfectivo))
          || planesRes.find(p => p.programa_id == null)
          || null;
        setPlanActual(plan);
      }
    } catch (err) {
      toast.error(err.message || "Error al enviar el Plan de Trabajo");
    } finally {
      e.target.value = '';
      uploadingTargetRef.current = null;
      setUploadingTarget(null);
    }
  };

  const getUnidadNombre = (carga) => {
    if (carga?.unidad_nombre) return carga.unidad_nombre;
    const udId = typeof carga === 'object' ? carga?.unidad_didactica_id : carga;
    const ud = mallaFlat.find(u => u.id === udId);
    return ud ? ud.nombre : `Unidad #${udId}`;
  };

  // Filtrar carga lectiva del periodo activo y programa
  const cargaActiva = cargaLectiva.filter(c => 
    (!selectedPeriod || String(c.periodo_id) === String(selectedPeriod)) &&
    (!programaEfectivo || String(c.programa_id) === String(programaEfectivo))
  );

  return (
    <div className="space-y-6">
      {/* Cabecera Informativa y Filtros del Docente */}
      <div className="glass-card p-4 grid grid-cols-1 md:grid-cols-2 gap-4 border-l-4 border-l-primary mb-6 bg-gradient-to-r from-white to-slate-50">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-full bg-primary-soft flex items-center justify-center text-primary flex-shrink-0">
            <GraduationCap className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <p className="text-[10px] uppercase font-extrabold text-slate-400 tracking-wider mb-1">Programa de Estudios</p>
            {programaBloqueado ? (
              <div
                className="w-full flex items-center gap-2 px-3 py-1.5 bg-slate-100 border border-slate-200 rounded-lg text-xs font-bold text-slate-800"
                title="La carrera está asignada a su cuenta y no puede modificarla."
              >
                <Lock size={12} className="text-slate-500 shrink-0" />
                <span className="truncate">{nombrePrograma || 'Carrera asignada'}</span>
                <span className="ml-auto shrink-0 text-[9px] font-black uppercase tracking-wider text-slate-500">Asignada</span>
              </div>
            ) : (
              <select
                className="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-800 focus:outline-none focus:ring-1 focus:ring-primary"
                value={selectedProgram}
                onChange={(e) => setSelectedProgram(e.target.value)}
              >
                <option value="">-- Seleccione Programa --</option>
                {programasVisibles.map((p) => (
                  <option key={p.id} value={p.id}>{p.nombre}</option>
                ))}
              </select>
            )}
            {!esAdminGlobal && !programaAsignado && programasCargaLectiva.length === 0 && (
              <p className="mt-1 flex items-start gap-1 text-[10px] font-semibold text-amber-700">
                <AlertTriangle size={11} className="mt-0.5 shrink-0" />
                <span>Su cuenta no tiene una carrera asignada. Contacte al administrador.</span>
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-full bg-primary-soft flex items-center justify-center text-primary flex-shrink-0">
            <Calendar className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <p className="text-[10px] uppercase font-extrabold text-slate-400 tracking-wider mb-1">Periodo Activo</p>
            <select
              className="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-800 focus:outline-none focus:ring-1 focus:ring-primary font-mono"
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(e.target.value)}
            >
              <option value="">-- Seleccione Periodo --</option>
              {periods.map((p) => (
                <option key={p.id} value={p.id}>{p.codigo} {p.estado ? `— ${p.estado.replace(/_/g, ' ')}` : ''}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Plan de Trabajo Global */}
          <div className="lg:col-span-1">
            <div className="glass-card p-6 h-full">
              <div className="flex items-center space-x-3 mb-6">
                <div className="w-10 h-10 rounded-xl bg-primary-soft flex items-center justify-center text-primary">
                  <ClipboardList className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-text">Plan de Trabajo</h3>
                  <p className="text-xs text-slate-500">Documento global del periodo</p>
                </div>
              </div>

              {planActual ? (
                <div className="bg-green-50/50 border border-green-100 rounded-xl p-4">
                  <div className="flex justify-between items-center mb-3">
                    <span className="text-sm font-bold text-green-700">Estado: {planActual.estado.toUpperCase()}</span>
                    <span className="bg-green-100 text-green-600 text-xs px-2 py-1 rounded-full flex items-center"><CheckCircle2 className="w-3 h-3 mr-1" /> Entregado</span>
                  </div>
                  <a 
                    href={planActual.archivo_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="flex items-center space-x-2 text-sm text-primary hover:text-primary-dark font-medium mb-3"
                  >
                    <ExternalLink className="w-4 h-4" />
                    <span>Ver Documento</span>
                  </a>
                  {planActual.observaciones && (
                    <div className="mt-3 bg-white p-3 rounded-lg border border-red-100">
                      <p className="text-xs font-bold text-red-600 mb-1">Observaciones del Coordinador:</p>
                      <p className="text-xs text-slate-600">{planActual.observaciones}</p>
                    </div>
                  )}
                  {planActual.estado !== 'aprobado' && (
                    <button 
                      onClick={triggerUploadPlan}
                      className="w-full mt-4 px-4 py-2 border border-slate-200 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
                    >
                      Actualizar Documento
                    </button>
                  )}
                </div>
              ) : (
                <div className="text-center p-6 bg-slate-50/50 rounded-xl border border-slate-100 border-dashed">
                  <div className="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-3 text-primary"><FileText className="w-6 h-6" /></div>
                  <p className="text-sm text-slate-500 mb-4">Aún no has presentado tu plan de trabajo para este periodo.</p>
                  <button 
                    onClick={triggerUploadPlan}
                    className="btn-primary w-full py-2 rounded-lg text-sm"
                  >
                    <Upload className="w-4 h-4 mr-1 inline" /> Subir Plan de Trabajo
                  </button>
                </div>
              )}
            </div>

            {/* Hidden File Inputs */}
            <input type="file" ref={fileInputRefSilabo} onChange={handleUploadSilabo} className="hidden" accept=".pdf,.doc,.docx,.xls,.xlsx" />
            <input type="file" ref={fileInputRefPlan} onChange={handleUploadPlan} className="hidden" accept=".pdf,.doc,.docx,.xls,.xlsx" />

          </div>

          {/* Carga Lectiva y Sílabos */}
          <div className="lg:col-span-2">
            <div className="glass-card p-6 h-full">
              <div className="flex items-center space-x-3 mb-6">
                <div className="w-10 h-10 rounded-xl bg-primary-soft flex items-center justify-center text-primary">
                  <BookOpen className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-text">Unidades Didácticas y Sílabos</h3>
                  <p className="text-xs text-slate-500">Carga lectiva asignada por el coordinador</p>
                </div>
              </div>

              {loading ? (
                <div className="text-center py-10">
                  <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
                </div>
              ) : cargaActiva.length === 0 ? (
                <div className="text-center p-8 bg-slate-50 rounded-xl border border-slate-100">
                  <p className="text-slate-500">No tienes carga lectiva asignada para este periodo en este programa.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {cargaActiva.map(carga => {
                    const udNombre = getUnidadNombre(carga);
                    const silabo = silabos.find(s => s.carga_lectiva_id === carga.id);

                    return (
                      <div key={carga.id} className="border border-slate-100 rounded-xl p-4 hover:shadow-md transition-shadow bg-white">
                        <div className="flex flex-col md:flex-row justify-between md:items-center">
                          <div className="mb-4 md:mb-0">
                            <h4 className="font-bold text-slate-text text-md">{udNombre}</h4>
                            <div className="flex items-center space-x-3 mt-1">
                              <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                                Turno: {carga.turno}
                              </span>
                              <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                                Sección: {carga.seccion}
                              </span>
                            </div>
                          </div>

                          <div className="flex items-center">
                            {silabo ? (
                              <div className="text-right">
                                <div className="flex items-center space-x-2 mb-1 justify-end">
                                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                                    silabo.estado === 'aprobado' ? 'bg-green-100 text-green-700' :
                                    silabo.estado === 'observado' ? 'bg-red-100 text-red-700' :
                                    'bg-blue-100 text-blue-700'
                                  }`}>
                                    {silabo.estado.toUpperCase()}
                                  </span>
                                </div>
                                <div className="flex space-x-2 items-center">
                                  <a href={silabo.archivo_url} target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:underline flex items-center"><ExternalLink className="w-3 h-3 mr-1" />Ver Doc</a>
                                  {silabo.estado !== 'aprobado' && (
                                    <button onClick={() => triggerUploadSilabo(carga.id)} className="text-xs text-slate-500 hover:text-slate-700 underline flex items-center">
                                      <RefreshCw className="w-3 h-3 mr-1" /> Actualizar
                                    </button>
                                  )}
                                </div>
                                {silabo.observaciones && (
                                  <p className="text-[10px] text-red-500 mt-1 max-w-[200px] truncate" title={silabo.observaciones}>
                                    Obs: {silabo.observaciones}
                                  </p>
                                )}
                              </div>
                            ) : (
                              <button 
                                onClick={() => triggerUploadSilabo(carga.id)}
                                className="flex items-center text-xs font-bold text-primary bg-primary-soft hover:bg-primary/20 px-3 py-1.5 rounded-lg transition-colors border border-primary/20"
                              >
                                <Upload className="w-4 h-4 mr-1" />
                                Subir Sílabo
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
    </div>
  );
}
