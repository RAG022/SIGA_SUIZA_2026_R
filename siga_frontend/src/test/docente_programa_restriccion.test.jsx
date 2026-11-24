import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { DocentePlanning } from '../modules/academic/DocentePlanning';
import { apiClient } from '../core/api/client';

// Docente con carrera asignada en su ficha (perfiles_personal.programa_estudio_id)
vi.mock('../core/auth/useAuth', () => ({
  useAuth: () => ({
    user: { id: 11, email: 'docente.dsi@siga.edu', full_name: 'Docente DSI', role: 'docente', programa_id: 22 },
    token: 'fake-jwt-token',
  }),
}));

vi.mock('../core/api/client', () => ({
  apiClient: { request: vi.fn() },
}));

const PROGRAMAS = [
  { id: 21, nombre: 'Mecatrónica automotriz' },
  { id: 22, nombre: 'DESARROLLO DE SISTEMAS DE INFORMACION' },
  { id: 23, nombre: 'Contabilidad' },
  { id: 24, nombre: 'Gestión Administrativa' },
  { id: 25, nombre: 'Enfermería Técnica' },
];

describe('DocentePlanning - restricción por carrera asignada', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('solo muestra la carrera del docente y no permite cambiarla', async () => {
    apiClient.request.mockImplementation((endpoint) => {
      if (endpoint === '/api/mod-programas-estudio/programas') return Promise.resolve(PROGRAMAS);
      if (endpoint === '/api/mod-programas-estudio/periodos') return Promise.resolve([{ id: 14, codigo: '2026-II', estado: 'matricula_abierta' }]);
      if (endpoint.includes('/carga-lectiva')) {
        return Promise.resolve([
          { id: 50, programa_id: 22, periodo_id: 14, unidad_didactica_id: 101, seccion: 'A', turno: 'M' },
        ]);
      }
      if (endpoint.includes('/malla')) {
        return Promise.resolve([{ id: 1, nombre: 'Módulo I', unidades: [{ id: 101, nombre: 'Taller Web' }] }]);
      }
      return Promise.resolve([]);
    });

    render(<DocentePlanning />);

    await waitFor(() => {
      expect(screen.getByText('DESARROLLO DE SISTEMAS DE INFORMACION')).toBeInTheDocument();
    });

    expect(screen.getByText('Asignada')).toBeInTheDocument();
    expect(screen.queryByText('Mecatrónica automotriz')).not.toBeInTheDocument();
    expect(screen.queryByText('Enfermería Técnica')).not.toBeInTheDocument();

    // La malla y la carga se consultan para la carrera asignada, no para otra.
    await waitFor(() => {
      expect(apiClient.request).toHaveBeenCalledWith('/api/mod-programas-estudio/programas/22/malla');
    });
    expect(apiClient.request).not.toHaveBeenCalledWith('/api/mod-programas-estudio/programas/21/malla');
  });
});
