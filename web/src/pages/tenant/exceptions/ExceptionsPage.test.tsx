import { screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { meterService } from '../../../api/services/meterService';
import { makeException } from '../../../test/meterFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { ExceptionsPage } from './ExceptionsPage';

const mocks = vi.hoisted(() => ({
  listExceptions: vi.fn<typeof meterService.listExceptions>(),
}));
vi.mock('../../../api/services/meterService', () => ({
  meterService: { listExceptions: mocks.listExceptions },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 }),
  },
}));

beforeEach(() => {
  mocks.listExceptions.mockResolvedValue({
    items: [makeException()],
    total: 1,
    page: 1,
    page_size: 25,
  });
});

describe('ExceptionsPage', () => {
  it('filters on the server by status and type only (no job filter)', async () => {
    renderWithProviders(<ExceptionsPage />, {
      tenantPermissions: ['tenant.meter.read'],
      route: '/tenant/exceptions?status=OPEN&job_id=59c43b66-da8f-4269-86dd-508629a63c19',
    });
    await waitFor(() => {
      expect(mocks.listExceptions).toHaveBeenCalled();
    });
    const [query] = mocks.listExceptions.mock.lastCall ?? [];
    expect(query?.filters).toMatchObject({ status: 'OPEN' });
    expect(query?.filters).not.toHaveProperty('job_id');
    expect(screen.queryByRole('combobox', { name: 'Job' })).not.toBeInTheDocument();
  });
});
