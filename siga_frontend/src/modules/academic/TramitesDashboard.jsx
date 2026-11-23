import { useState, useEffect, useMemo } from 'react';
import { apiClient } from '../../core/api/client';
import { useToast } from '../../core/ui/ToastContext';
import { Plus, Eye, FileText, Repeat, GraduationCap, Search, X } from 'lucide-react';
import { ConvalidacionesTab } from './ConvalidacionesTab';
import { BecasTab } from './BecasTab';

const TIPOS_TRAMITE = [
  'Constancia de Estudios',
  'Certificado Modular',
  'Certificado de Estudios',
  'Reserva de Matrícula',
  'Retiro de Unidad Didáctica',
  'Rectificación de Datos',
  'Reingreso',
  'Traslado Interno / Externo',
  'Licencia de Estudios',
  'Otro Trámite TUPA',
];

const FORM_NUEVA_VACIO = {
  estudiante_id: '',
  tipo_tramite: TIPOS_TRAMITE[0],
  observaciones: '',
};

export function TramitesDashboard() {
  const toast = useToast();
  const [activeTab, setActiveTab] = useState('solicitudes');
  const [loading, setLoading] = useState(false);

  // States for Solicitudes (TUPA)
  const [solicitudes, setSolicitudes] = useState([]);
  const [estudiantes, setEstudiantes] = useState([]);
  const [error, setError] = useState('');

  // Search & filter
  const [searchTerm, setSearchTerm] = useState('');
  const [filterEstado, setFilterEstado] = useState('todos');

  // Modals: Nueva Solicitud & Ver Detalles
  const [showNewModal, setShowNewModal] = useState(false);
  const [newForm, setNewForm] = useState(FORM_NUEVA_VACIO);
  const [studentSearch, setStudentSearch] = useState('');
  const [savingNew, setSavingNew] = useState(false);
  const [selectedSolicitud, setSelectedSolicitud] = useState(null);

  const fetchSolicitudes = async () => {
    setLoading(true);
    setError('');
    try {
      const [tramites, estList] = await Promise.all([
        apiClient.request('/api/mod-gestion-academica/tramites/'),
        apiClient.request('/api/mod-gestion-academica/estudiantes/').catch(() => []),
      ]);
      const estArr = Array.isArray(estList) ? estList : [];
      setEstudiantes(estArr);
      const estMap = new Map(estArr.map(e => [e.id, e]));
      setSolicitudes((tramites || []).map(t => {
        const est = estMap.get(t.estudiante_id);
        return {
          ...t,
          nombre_alumno: est ? `${est.apellidos}, ${est.nombres}` : undefined,
          dni_alumno: est?.dni || '',
        };
      }));
    } catch (err) {
      console.error(err);
      setError('No se pudieron cargar los trámites.');
      setSolicitudes([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'solicitudes') {
      fetchSolicitudes();
    }
  }, [activeTab]);

  const solicitudesFiltradas = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return solicitudes.filter(s => {
      const matchEstado = filterEstado === 'todos' || s.estado === filterEstado;
      if (!matchEstado) return false;
      if (!q) return true;
      return (
        String(s.id).includes(q) ||
        (s.nombre_alumno || '').toLowerCase().includes(q) ||
        (s.dni_alumno || '').toLowerCase().includes(q) ||
        (s.tipo_tramite || '').toLowerCase().includes(q) ||
        (s.observaciones || '').toLowerCase().includes(q)
      );
    });
  }, [solicitudes, searchTerm, filterEstado]);

  const estudiantesFiltrados = useMemo(() => {
    const q = studentSearch.trim().toLowerCase();
    if (!q) return estudiantes.slice(0, 100);
    return estudiantes
      .filter(e =>
        `${e.apellidos} ${e.nombres}`.toLowerCase().includes(q) ||
        String(e.dni || '').toLowerCase().includes(q) ||
        String(e.codigo_estudiante || '').toLowerCase().includes(q)
      )
      .slice(0, 100);
  }, [estudiantes, studentSearch]);

  const handleEstadoChange = async (id, newEstado) => {
    const anterior = solicitudes;
    setSolicitudes(prev => prev.map(s => s.id === id ? { ...s, estado: newEstado } : s));
    try {
      const updated = await apiClient.request(
        `/api/mod-gestion-academica/tramites/${id}/estado?estado=${encodeURIComponent(newEstado)}`,
        { method: 'PUT' }
      );
      if (updated) {
        setSolicitudes(prev => prev.map(s => s.id === id ? { ...s, estado: updated.estado, fecha_resolucion: updated.fecha_resolucion } : s));
      }
      toast.success(`Estado del trámite #${id} actualizado a "${newEstado.replace('_', ' ')}".`);
    } catch (err) {
      console.error(err);
      setSolicitudes(anterior);
      setError('No se pudo actualizar el estado del trámite.');
      toast.error(err.message || 'No se pudo actualizar el estado del trámite.');
    }
  };

  const handleCreateSolicitud = async (e) => {
    e.preventDefault();
    if (!newForm.estudiante_id) {
      toast.warning('Seleccione un estudiante para registrar la solicitud.');
      return;
    }
    if (!newForm.tipo_tramite.trim()) {
      toast.warning('Indique el tipo de trámite.');
      return;
    }
    setSavingNew(true);
    try {
      await apiClient.request('/api/mod-gestion-academica/tramites/', {
        method: 'POST',
        body: JSON.stringify({
          estudiante_id: parseInt(newForm.estudiante_id, 10),
          tipo_tramite: newForm.tipo_tramite.trim(),
          observaciones: newForm.observaciones.trim() || null,
        }),
      });
      toast.success('Solicitud registrada correctamente.');
      setShowNewModal(false);
      setNewForm(FORM_NUEVA_VACIO);
      setStudentSearch('');
      await fetchSolicitudes();
    } catch (err) {
      console.error(err);
      toast.error(err.message || 'No se pudo registrar la solicitud.');
    } finally {
      setSavingNew(false);
    }
  };

  const renderTabHeader = (id, label, icon) => (
    <button
      onClick={() => setActiveTab(id)}
      className={`px-5 py-3 rounded-t-xl font-bold transition-colors flex items-center space-x-2 cursor-pointer ${
        activeTab === id
          ? 'bg-white text-primary border-t-2 border-primary shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)] z-10 relative'
          : 'bg-slate-100 text-slate-500 hover:bg-slate-200 border-b border-slate-300'
      }`}
    >
      <span>{icon}</span>
      <span>{label}</span>
    </button>
  );

  return (
    <div className="animate-fade-in space-y-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center">
        <div>
          <h3 className="text-3xl font-bold tracking-tight text-slate-text">
            Gestión de <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-500 to-orange-500">Trámites y Casuísticas</span>
          </h3>
          <p className="text-slate-500 text-sm mt-1">Administración TUPA, Convalidaciones, Becas y Resoluciones</p>
        </div>
      </div>

      <div className="w-full">
        <div className="flex border-b-0 space-x-1">
          {renderTabHeader('solicitudes', 'Trámites y Solicitudes', <FileText size={16} />)}
          {renderTabHeader('convalidaciones', 'Convalidaciones', <Repeat size={16} />)}
          {renderTabHeader('becas', 'Becas y Beneficios', <GraduationCap size={16} />)}
        </div>

        <div className="glass-card rounded-tl-none p-6 min-h-[500px]">
          {activeTab === 'solicitudes' && (
            <div className="space-y-5 animate-fade-in">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                <h4 className="text-lg font-bold text-slate-700">Solicitudes Ingresadas</h4>
                <button
                  type="button"
                  onClick={() => {
                    setNewForm(FORM_NUEVA_VACIO);
                    setStudentSearch('');
                    setShowNewModal(true);
                  }}
                  className="btn-primary py-1.5 px-4 text-sm rounded-lg flex items-center gap-1.5 cursor-pointer"
                >
                  <Plus size={16} /> Nueva Solicitud Manual
                </button>
              </div>

              {/* Buscador y filtro por estado */}
              <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center">
                <div className="relative flex-1">
                  <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                  <input
                    type="text"
                    className="input-field w-full pl-9 pr-8 py-2 text-sm"
                    placeholder="Buscar por estudiante, DNI, tipo de trámite o #ID..."
                    value={searchTerm}
                    onChange={e => setSearchTerm(e.target.value)}
                  />
                  {searchTerm && (
                    <button
                      type="button"
                      onClick={() => setSearchTerm('')}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                      aria-label="Limpiar búsqueda"
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>
                <select
                  className="input-field py-2 text-sm sm:w-48"
                  value={filterEstado}
                  onChange={e => setFilterEstado(e.target.value)}
                >
                  <option value="todos">Todos los estados</option>
                  <option value="pendiente">Pendiente</option>
                  <option value="en_proceso">En Proceso</option>
                  <option value="emitido">Emitido / Aprobado</option>
                  <option value="rechazado">Rechazado</option>
                </select>
              </div>

              {error && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</div>}
              {loading ? (
                <div className="text-center py-10"><div className="w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto"></div></div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm border-collapse">
                    <thead className="bg-slate-50/80 border-y border-slate-200">
                      <tr>
                        <th className="py-3 px-4 font-bold text-slate-600">ID / Fecha</th>
                        <th className="py-3 px-4 font-bold text-slate-600">Estudiante</th>
                        <th className="py-3 px-4 font-bold text-slate-600">Tipo de Trámite</th>
                        <th className="py-3 px-4 font-bold text-slate-600">Estado</th>
                        <th className="py-3 px-4 font-bold text-slate-600 text-right">Acciones</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {solicitudesFiltradas.length === 0 && (
                        <tr>
                          <td colSpan={5} className="py-10 text-center text-slate-400">
                            {solicitudes.length === 0 ? 'No hay solicitudes registradas.' : 'No se encontraron solicitudes con los filtros aplicados.'}
                          </td>
                        </tr>
                      )}
                      {solicitudesFiltradas.map(s => (
                        <tr key={s.id} className="hover:bg-primary/5 transition-colors">
                          <td className="py-3 px-4">
                            <span className="font-semibold text-slate-700">#{s.id}</span>
                            <div className="text-xs text-slate-500">{s.fecha_solicitud}</div>
                          </td>
                          <td className="py-3 px-4 font-semibold text-slate-700">
                            <div>{s.nombre_alumno || `Estudiante #${s.estudiante_id}`}</div>
                            {s.dni_alumno && <div className="text-xs font-mono text-slate-400">DNI {s.dni_alumno}</div>}
                          </td>
                          <td className="py-3 px-4 font-medium text-slate-600">{s.tipo_tramite}</td>
                          <td className="py-3 px-4">
                            <span className={`badge ${
                              s.estado === 'pendiente' ? 'badge-amber' :
                              s.estado === 'en_proceso' ? 'badge-blue' :
                              s.estado === 'emitido' ? 'badge-green' :
                              'badge-slate'
                            }`}>
                              {s.estado.replace('_', ' ')}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right whitespace-nowrap">
                            <select
                              className="input-field text-xs mr-2 py-1.5"
                              value={s.estado}
                              onChange={(e) => handleEstadoChange(s.id, e.target.value)}
                            >
                              <option value="pendiente">Pendiente</option>
                              <option value="en_proceso">En Proceso</option>
                              <option value="emitido">Emitido / Aprobado</option>
                              <option value="rechazado">Rechazado</option>
                            </select>
                            <button
                              type="button"
                              onClick={() => setSelectedSolicitud(s)}
                              className="btn-icon text-slate-400 hover:text-amber-600 cursor-pointer"
                              title="Ver Detalles"
                            >
                              <Eye size={18} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {activeTab === 'convalidaciones' && <ConvalidacionesTab />}

          {activeTab === 'becas' && <BecasTab />}
        </div>
      </div>

      {/* Modal: Nueva Solicitud Manual */}
      {showNewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-lg overflow-hidden">
            <div className="flex justify-between items-center px-6 py-4 border-b border-slate-100">
              <div>
                <h5 className="font-bold text-base text-slate-900">Nueva Solicitud Manual (TUPA)</h5>
                <p className="text-xs text-slate-400">Registra un trámite institucional para un estudiante</p>
              </div>
              <button
                type="button"
                onClick={() => setShowNewModal(false)}
                className="text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-100"
              >
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleCreateSolicitud} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Buscar Estudiante (DNI o Apellidos)</label>
                <input
                  type="text"
                  className="input-field w-full text-sm mb-2"
                  placeholder="Filtrar lista de estudiantes..."
                  value={studentSearch}
                  onChange={e => setStudentSearch(e.target.value)}
                />
                <select
                  className="input-field w-full text-sm"
                  value={newForm.estudiante_id}
                  onChange={e => setNewForm({ ...newForm, estudiante_id: e.target.value })}
                  required
                >
                  <option value="">Seleccione un estudiante...</option>
                  {estudiantesFiltrados.map(e => (
                    <option key={e.id} value={e.id}>
                      {e.apellidos}, {e.nombres} ({e.dni})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Tipo de Trámite</label>
                <select
                  className="input-field w-full text-sm"
                  value={newForm.tipo_tramite}
                  onChange={e => setNewForm({ ...newForm, tipo_tramite: e.target.value })}
                  required
                >
                  {TIPOS_TRAMITE.map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Observaciones / Motivo</label>
                <textarea
                  rows={3}
                  className="input-field w-full text-sm"
                  placeholder="Detalles adicionales de la solicitud, número de expediente o sustento..."
                  value={newForm.observaciones}
                  onChange={e => setNewForm({ ...newForm, observaciones: e.target.value })}
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowNewModal(false)}
                  className="px-4 py-2 rounded-xl border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                  disabled={savingNew}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="btn-primary px-5 py-2 text-xs font-bold rounded-xl"
                  disabled={savingNew}
                >
                  {savingNew ? 'Registrando...' : 'Registrar Solicitud'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Detalle de Solicitud */}
      {selectedSolicitud && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-md overflow-hidden">
            <div className="flex justify-between items-center px-6 py-4 border-b border-slate-100">
              <div>
                <h5 className="font-bold text-base text-slate-900">Detalle de Trámite #{selectedSolicitud.id}</h5>
                <p className="text-xs text-slate-400">{selectedSolicitud.tipo_tramite}</p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedSolicitud(null)}
                className="text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-100"
              >
                <X size={18} />
              </button>
            </div>
            <div className="p-6 space-y-3 text-sm">
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500 font-medium">Estudiante:</span>
                <span className="font-bold text-slate-800">{selectedSolicitud.nombre_alumno || `Estudiante #${selectedSolicitud.estudiante_id}`}</span>
              </div>
              {selectedSolicitud.dni_alumno && (
                <div className="flex justify-between py-1.5 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">DNI:</span>
                  <span className="font-mono font-bold text-slate-800">{selectedSolicitud.dni_alumno}</span>
                </div>
              )}
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500 font-medium">Estado:</span>
                <span className="font-bold uppercase text-xs text-primary">{selectedSolicitud.estado.replace('_', ' ')}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500 font-medium">Fecha Solicitud:</span>
                <span className="text-slate-700">{selectedSolicitud.fecha_solicitud || '—'}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500 font-medium">Fecha Resolución:</span>
                <span className="text-slate-700">{selectedSolicitud.fecha_resolucion || 'Pendiente'}</span>
              </div>
              <div className="pt-1">
                <span className="block text-slate-500 font-medium mb-1">Observaciones:</span>
                <p className="text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded-xl p-3">
                  {selectedSolicitud.observaciones || 'Sin observaciones registradas.'}
                </p>
              </div>
            </div>
            <div className="px-6 py-3 bg-slate-50 border-t border-slate-100 flex justify-end">
              <button
                type="button"
                onClick={() => setSelectedSolicitud(null)}
                className="px-4 py-2 rounded-xl bg-slate-900 text-white text-xs font-semibold hover:bg-slate-800"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
