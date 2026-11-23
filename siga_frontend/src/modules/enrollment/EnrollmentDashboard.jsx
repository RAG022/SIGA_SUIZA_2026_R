import { useState, useEffect, useMemo } from 'react';
import {
  UserPlus, UserCog, QrCode, Scale, HeartHandshake,
  ShieldAlert, Trophy, Users, FolderOpen, PlusCircle, GraduationCap,
} from 'lucide-react';
import { API_BASE } from '../../core/api/client';
import { useAuth } from '../../core/auth/useAuth';
import { useProgramas } from '../students/useProgramas';
import { EnrollmentProcess } from './EnrollmentProcess';
import { EnrollmentFlowDiagram } from './EnrollmentFlowDiagram';
import { AdmissionPanel } from './AdmissionPanel';
import { TiposAlumnosPanel } from './TiposAlumnosPanel';
import { BoletaQRPanel } from './BoletaQRPanel';
import { DeterminacionPanel } from './DeterminacionPanel';
import { EspecialesPanel } from './EspecialesPanel';
import { RestriccionesPanel } from './RestriccionesPanel';
import { ResultadoPanel } from './ResultadoPanel';
import ExtraordinaryEnrollmentModal from './ExtraordinaryEnrollmentModal';
import { SectionInfoBlock } from './SectionInfoBlock';
import './enrollmentPremium.css';

export function EnrollmentDashboard() {
  const { user } = useAuth();
  const userRoles = user?.roles ? user.roles.map(r => typeof r === 'string' ? r : r.nombre || r.name) : [];
  const primaryRole = user?.is_superuser ? 'superadmin' : (userRoles.length > 0 ? userRoles[0] : (user?.role || 'invitado'));
  const userRole = primaryRole;
  const { programas } = useProgramas();
  const esRolRestringido = !user?.is_superuser && userRoles.some(r => ['secretaria_programa', 'secretaria_academica', 'coordinador_programa'].includes(r));
  const programaRestringido = esRolRestringido && user?.programa_id ? String(user.programa_id) : null;

  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [view, setView] = useState('list'); // 'list', 'process' or 'diagram'
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPrograma, setCurrentPrograma] = useState('ALL');
  const programaEfectivo = programaRestringido ?? currentPrograma;

  const programaOptions = useMemo(
    () => [{ id: 'ALL', label: 'Todos los Programas' }, ...programas],
    [programas]
  );

  const programaLabel = (id) => {
    const p = programaOptions.find(o => String(o.id) === String(id));
    return p ? p.label : (id ? `Programa ${id}` : 'Todos los Programas');
  };

  const fetchStudents = async () => {
    setLoading(true);
    setLoadError('');
    try {
      let url = `${API_BASE}/api/mod-gestion-academica/estudiantes/`;
      if (programaEfectivo && programaEfectivo !== 'ALL') {
        url += `?programa_id=${encodeURIComponent(programaEfectivo)}`;
      }
      
      const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      if (!response.ok) {
        const errBody = await response.json().catch(() => ({}));
        throw new Error(errBody.detail || `Error HTTP ${response.status} al cargar estudiantes.`);
      }
      const data = await response.json();
      setStudents(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Error fetching students:', error);
      setStudents([]);
      setLoadError(error.message || 'No se pudieron cargar los estudiantes.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (userRole !== 'invitado') {
      fetchStudents();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [programaEfectivo, userRole]);

  const filteredStudents = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    if (q.length < 2) return students;
    return students.filter(s =>
      (s.dni && s.dni.toLowerCase().includes(q)) ||
      (s.nombres && s.nombres.toLowerCase().includes(q)) ||
      (s.apellidos && s.apellidos.toLowerCase().includes(q)) ||
      (s.codigo_estudiante && s.codigo_estudiante.toLowerCase().includes(q)) ||
      `${s.apellidos || ''} ${s.nombres || ''}`.toLowerCase().includes(q)
    );
  }, [students, searchTerm]);

  const handleEnrollClick = (student) => {
    setSelectedStudent(student);
    setView('process');
  };

  if (view === 'process') {
    return (
      <EnrollmentProcess 
        initialStudent={selectedStudent} 
        onCancel={() => {
          setView('list');
          setSelectedStudent(null);
          fetchStudents(); // Refrescar en caso de matrícula exitosa
        }} 
      />
    );
  }

  const tabs = [
    { id: 'admision', label: 'Admisión', Icon: UserPlus },
    { id: 'tipos', label: 'Tipos de alumnos', Icon: UserCog },
    { id: 'boleta', label: 'Boleta con QR', Icon: QrCode },
    { id: 'determinacion', label: 'Determinación', Icon: Scale },
    { id: 'especiales', label: 'Alumnos especiales', Icon: HeartHandshake },
    { id: 'restricciones', label: 'Restricciones', Icon: ShieldAlert },
    { id: 'resultado', label: 'Resultado final', Icon: Trophy },
    { id: 'list', label: 'Estudiantes', Icon: Users },
    { id: 'diagram', label: 'Diagrama de flujo', Icon: FolderOpen },
  ];

  return (
    <div className="sma-page animate-fade-in">
      {/* Capa decorativa de fondo (ondas, blobs y patrón de puntos) */}
      <div className="sma-deco" aria-hidden="true">
        <span className="sma-blob sma-blob--a" />
        <span className="sma-blob sma-blob--b" />
        <span className="sma-dots sma-dots--tl" />
        <span className="sma-dots sma-dots--br" />
        <svg className="sma-waves" viewBox="0 0 1440 180" preserveAspectRatio="none">
          <path d="M0,104 C240,168 480,44 720,84 C960,124 1200,172 1440,112 L1440,180 L0,180 Z" fill="rgba(0,102,232,0.08)" />
          <path d="M0,128 C260,64 520,156 780,124 C1040,92 1240,52 1440,96 L1440,180 L0,180 Z" fill="rgba(0,157,255,0.10)" />
        </svg>
      </div>

      {/* Header institucional */}
      <header className="sma-header">
        <div className="sma-header-deco" aria-hidden="true">
          <span className="sma-hd-glow" />
          <span className="sma-hd-bar sma-hd-bar--1" />
          <span className="sma-hd-bar sma-hd-bar--2" />
          <span className="sma-hd-bar sma-hd-bar--3" />
          <span className="sma-hd-ring" />
        </div>

        {/* Birrete académico decorativo */}
        <svg className="sma-birrete" viewBox="0 0 64 64" fill="none" aria-hidden="true">
          <path d="M32 7 L61 20 L32 33 L3 20 Z" fill="#FFFFFF" opacity="0.96" />
          <path d="M32 24.5 L48 17.5" stroke="#55C7FF" strokeWidth="2" strokeLinecap="round" opacity="0.9" />
          <path d="M15 26.2 V38.5 C15 38.5 22.2 46.5 32 46.5 C41.8 46.5 49 38.5 49 38.5 V26.2" stroke="#FFFFFF" strokeWidth="4.2" strokeLinecap="round" fill="none" opacity="0.92" />
          <path d="M57.5 22.5 V39" stroke="#55C7FF" strokeWidth="3.4" strokeLinecap="round" />
          <circle cx="57.5" cy="42.6" r="3.1" fill="#55C7FF" />
        </svg>

        <div className="sma-header-body">
          <div>
            <h3 className="sma-title">
              Gestión de <span>Matrícula Académica</span>
            </h3>
            <p className="sma-subtitle">
              Control de procesos de matrícula para estudiantes registrados
            </p>
            {view === 'list' && (
              <div className="sma-header-actions">
                <button
                  onClick={() => setIsModalOpen(true)}
                  className="sma-header-btn"
                >
                  <PlusCircle size={18} />
                  Matrícula Extraordinaria
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Nueve pestañas */}
      <nav className="sma-tabs" role="tablist" aria-label="Secciones de gestión de matrícula">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            onClick={() => setView(tab.id)}
            aria-current={view === tab.id}
            aria-selected={view === tab.id}
            className={`sma-tab ${view === tab.id ? 'sma-tab--active' : ''}`}
          >
            <span className="sma-tab-icon"><tab.Icon size={17} /></span>
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="sma-content">
      {view === 'diagram' ? (
        <EnrollmentFlowDiagram />
      ) : view === 'admision' ? (
        <AdmissionPanel />
      ) : view === 'tipos' ? (
        <TiposAlumnosPanel />
      ) : view === 'boleta' ? (
        <BoletaQRPanel />
      ) : view === 'determinacion' ? (
        <DeterminacionPanel />
      ) : view === 'especiales' ? (
        <EspecialesPanel />
      ) : view === 'restricciones' ? (
        <RestriccionesPanel />
      ) : view === 'resultado' ? (
        <ResultadoPanel />
      ) : (
        <>
      <SectionInfoBlock
        className="mb-6"
        icon={Users}
        ghostIcon={GraduationCap}
        title="8. Estudiantes"
        description={
          <>
            Permite visualizar y consultar la información de los estudiantes registrados en el proceso
            de <b>matrícula académica</b>.
          </>
        }
        chips={['Consulta', 'Búsqueda', 'Matrícula']}
      />

      <div className="glass-card p-2 mb-8 flex items-center max-w-3xl gap-2">
        {!esRolRestringido && ['superadmin', 'admin'].includes(userRole) && (
          <select 
            className="input-field py-3 text-sm bg-slate-50 border-none w-48 font-bold text-primary"
            value={currentPrograma}
            onChange={(e) => {
              setCurrentPrograma(e.target.value);
            }}
          >
            {programaOptions.map(p => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
        )}
        {programaRestringido && (
          <span className="px-3 py-2 rounded-xl bg-primary/10 text-primary text-xs font-bold whitespace-nowrap">
            {programaLabel(programaRestringido)}
          </span>
        )}
        <span className="px-4 text-slate-400 text-xl">🔍</span>
        <input 
          type="text" 
          className="w-full bg-transparent border-none focus:ring-0 py-3 text-slate-700 placeholder-slate-400 outline-none"
          placeholder="Buscar por DNI, Nombre o Código..."
          value={searchTerm} 
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        {loading && <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin mx-4"></div>}
      </div>

      {loadError && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 font-medium">
          {loadError}
        </div>
      )}

      <div className="glass-card p-6">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="py-4 px-4 text-xs font-bold text-slate-400 uppercase tracking-wider w-[12%]">Código</th>
                <th className="py-4 px-4 text-xs font-bold text-slate-400 uppercase tracking-wider w-[35%]">Estudiante</th>
                <th className="py-4 px-4 text-xs font-bold text-slate-400 uppercase tracking-wider w-[13%]">DNI</th>
                <th className="py-4 px-4 text-xs font-bold text-slate-400 uppercase tracking-wider w-[15%] max-w-[150px]">Email</th>
                <th className="py-4 px-4 text-xs font-bold text-slate-400 uppercase tracking-wider w-[10%]">Estado</th>
                <th className="py-4 px-4 text-xs font-bold text-slate-400 uppercase tracking-wider text-right w-[15%]">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan="6" className="py-12 text-center">
                    <div className="inline-block w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mb-2"></div>
                    <p className="text-slate-500 font-medium">Cargando estudiantes...</p>
                  </td>
                </tr>
              ) : filteredStudents.length === 0 ? (
                <tr>
                  <td colSpan="6" className="py-12 text-center">
                    <div className="text-4xl mb-3 opacity-50">🎓</div>
                    <p className="text-slate-500 font-medium">No hay estudiantes registrados.</p>
                  </td>
                </tr>
              ) : (
                filteredStudents.map(student => (
                  <tr key={student.id} className="hover:bg-slate-50 transition-colors">
                    <td className="py-3 px-4 font-bold text-slate-700">{student.codigo_estudiante}</td>
                    <td className="py-3 px-4 text-slate-800 font-medium">{student.nombres} {student.apellidos}</td>
                    <td className="py-3 px-4 text-slate-600">{student.dni}</td>
                    <td className="py-3 px-4 text-slate-500 text-sm truncate max-w-[150px]" title={student.email_personal}>{student.email_personal || '-'}</td>
                    <td className="py-3 px-4">
                      <span className="inline-block px-2 py-1 bg-green-100 text-green-700 text-[10px] font-bold uppercase rounded border border-green-200">
                        {student.estado_academico}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button 
                        className="px-4 py-1.5 text-sm font-semibold text-primary bg-primary/10 hover:bg-primary/20 rounded-lg transition-colors"
                        onClick={() => handleEnrollClick(student)}
                      >
                        Matricular
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <ExtraordinaryEnrollmentModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        currentPrograma={programaEfectivo}
        userRole={userRole}
        onSuccess={(student) => {
          handleEnrollClick(student);
        }}
      />
        </>
      )}
      </div>
    </div>
  );
}
