import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../access/permissionCodes';
import { ApiError } from '../../api/ApiError';
import {
  exportError,
  filenameFromDisposition,
  type reportService,
} from '../../api/services/reportService';
import type { ReportDefinitionDto } from '../../api/types';
import { renderWithProviders } from '../../test/renderWithProviders';
import { exportParams } from './exportFile';
import { ExportMenu } from './ExportMenu';

const mocks = vi.hoisted(() => ({
  listDefinitions: vi.fn<typeof reportService.listDefinitions>(),
  download: vi.fn<typeof reportService.download>(),
}));
vi.mock('../../api/services/reportService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/services/reportService')>()),
  reportService: mocks,
}));

function definition(overrides: Partial<ReportDefinitionDto> = {}): ReportDefinitionDto {
  return {
    code: 'jobs',
    title: 'Jobs',
    description: 'Rental jobs',
    formats: ['csv', 'pdf'],
    csv_path: '/api/v1/tenant/reports/jobs.csv',
    pdf_path: '/api/v1/tenant/reports/jobs.pdf',
    list_operation: 'listJobs',
    filters: ['q', 'status', 'machine_id'],
    columns: [],
    csv_row_cap: 10000,
    pdf_row_cap: 2000,
    ...overrides,
  };
}

const createObjectURL = vi.fn(() => 'blob:report');
const revokeObjectURL = vi.fn();

beforeEach(() => {
  mocks.listDefinitions.mockResolvedValue([definition()]);
  mocks.download.mockResolvedValue({
    blob: new Blob(['a,b']),
    filename: 'asseta-jobs-2026-10-22.csv',
    rows: 42,
    truncated: false,
  });
  Object.assign(URL, { createObjectURL, revokeObjectURL });
});

afterEach(() => {
  createObjectURL.mockClear();
});

function renderMenu(filters: Record<string, string | undefined> = {}) {
  return renderWithProviders(
    <ExportMenu
      reports={[
        { code: 'jobs', filters },
        { code: 'readings', filters: { machine_id: 'm1' } },
      ]}
    />,
    { tenantPermissions: [P.tenantJobRead] },
  );
}

describe('ExportMenu', () => {
  it('lists only the reports the caller may export, as CSV and PDF', async () => {
    const user = userEvent.setup();
    renderMenu();
    await user.click(await screen.findByRole('button', { name: 'Export' }));
    const items = screen.getAllByRole('menuitem').map((i) => i.textContent);
    expect(items).toEqual([
      expect.stringContaining('Jobs (CSV)'),
      expect.stringContaining('Jobs (PDF)'),
    ]);
    expect(mocks.listDefinitions).toHaveBeenCalledWith('tenant', expect.any(String));
  });

  it('renders nothing when no requested report is permitted', async () => {
    mocks.listDefinitions.mockResolvedValue([definition({ code: 'cash', title: 'Cash' })]);
    renderMenu();
    await waitFor(() => {
      expect(mocks.listDefinitions).toHaveBeenCalled();
    });
    expect(screen.queryByRole('button', { name: 'Export' })).not.toBeInTheDocument();
  });

  it('downloads with the page filters the report accepts and saves the file', async () => {
    const user = userEvent.setup();
    renderMenu({ q: 'J-1', status: 'IN_PROGRESS', machine_id: '', sort: '-created_at' });
    await user.click(await screen.findByRole('button', { name: 'Export' }));
    await user.click(screen.getByRole('menuitem', { name: /Jobs \(CSV\)/ }));
    await waitFor(() => {
      expect(mocks.download).toHaveBeenCalledWith('tenant', 'jobs', 'csv', {
        q: 'J-1',
        status: 'IN_PROGRESS',
      });
    });
    expect(createObjectURL).toHaveBeenCalled();
    expect(await screen.findByText('Jobs: exported 42 rows.')).toBeInTheDocument();
  });

  it('shows the truncation notice from the response headers', async () => {
    const user = userEvent.setup();
    mocks.download.mockResolvedValue({
      blob: new Blob(['x']),
      filename: 'asseta-jobs.pdf',
      rows: 2000,
      truncated: true,
    });
    renderMenu();
    await user.click(await screen.findByRole('button', { name: 'Export' }));
    await user.click(screen.getByRole('menuitem', { name: /Jobs \(PDF\)/ }));
    expect(
      await screen.findByText(/export truncated to the first 2,000 rows \(PDF limit\)/),
    ).toBeInTheDocument();
  });

  it('reports a failed export', async () => {
    const user = userEvent.setup();
    mocks.download.mockRejectedValue(
      new ApiError({
        status: 403,
        code: 'FORBIDDEN',
        message: 'Missing permission',
        correlationId: 'c-1',
      }),
    );
    renderMenu();
    await user.click(await screen.findByRole('button', { name: 'Export' }));
    await user.click(screen.getByRole('menuitem', { name: /Jobs \(CSV\)/ }));
    expect(await screen.findByText(/Missing permission/)).toBeInTheDocument();
    expect(createObjectURL).not.toHaveBeenCalled();
  });
});

describe('export helpers', () => {
  it('keeps only the report filters, without empty values', () => {
    expect(
      exportParams(definition({ filters: ['status', 'from'] }), {
        status: 'OPEN',
        from: '',
        alert_type: 'X',
      }),
    ).toEqual({ status: 'OPEN' });
  });

  it('reads the file name from Content-Disposition', () => {
    expect(filenameFromDisposition('attachment; filename="asseta-cash-2026-10-22.csv"', 'f')).toBe(
      'asseta-cash-2026-10-22.csv',
    );
    expect(filenameFromDisposition("attachment; filename*=UTF-8''r%C3%A9sum%C3%A9.pdf", 'f')).toBe(
      'résumé.pdf',
    );
    expect(filenameFromDisposition(null, 'fallback.csv')).toBe('fallback.csv');
  });

  it('turns a JSON error body delivered as a Blob into an ApiError', async () => {
    const body = new Blob([
      JSON.stringify({
        error: { code: 'INVALID_RANGE', message: 'Bad period', correlation_id: 'x', details: [] },
      }),
    ]);
    const err = await exportError(422, body);
    expect(err.code).toBe('INVALID_RANGE');
    expect(err.message).toBe('Bad period');
    expect((await exportError(500, new Blob(['oops']))).code).toBe('export_failed');
  });
});
