import { screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { jobService } from '../../../api/services/jobService';
import type { meterService } from '../../../api/services/meterService';
import { makeException, makeJob, makeSummary } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { ExceptionsPage } from './ExceptionsPage';

const JOB_ID = '59c43b66-da8f-4269-86dd-508629a63c19';
const mocks = vi.hoisted(() => ({
  listExceptions: vi.fn<typeof meterService.listExceptions>(),
  jobs: vi.fn<typeof jobService.list>(),
  summary: vi.fn<typeof jobService.summary>(),
}));
vi.mock('../../../api/services/meterService', () => ({
  meterService: { listExceptions: mocks.listExceptions },
}));
vi.mock('../../../api/services/jobService', () => ({
  jobService: { list: mocks.jobs, summary: mocks.summary },
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
  mocks.jobs.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
});

function renderDeepLink() {
  renderWithProviders(<ExceptionsPage />, {
    tenantPermissions: ['tenant.meter.read'],
    route: `/tenant/exceptions?job_id=${JOB_ID}`,
  });
}

describe('ExceptionsPage', () => {
  it('shows a job_id deep link by its job number and filters on the server', async () => {
    mocks.summary.mockResolvedValue(
      makeSummary({ job: makeJob({ id: JOB_ID, job_number: 'J-1001' }) }),
    );
    renderDeepLink();
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: 'Job' })).toHaveValue('J-1001');
    });
    expect(mocks.summary).toHaveBeenCalledWith(JOB_ID, expect.any(AbortSignal));
    const [query] = mocks.listExceptions.mock.lastCall ?? [];
    expect(query?.filters).toMatchObject({ job_id: JOB_ID });
    expect(screen.queryByText(/59c43b66/)).not.toBeInTheDocument();
  });

  it('keeps a removable neutral chip when the linked job cannot be loaded', async () => {
    mocks.summary.mockRejectedValue(
      new ApiError({
        status: 404,
        code: 'NOT_FOUND',
        message: 'Not found',
        correlationId: null,
        details: [],
      }),
    );
    renderDeepLink();
    expect(await screen.findByText('Filtered by one job')).toBeInTheDocument();
    expect(screen.queryByText(/59c43b66/)).not.toBeInTheDocument();
  });
});
