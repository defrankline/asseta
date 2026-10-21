import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { jobService } from '../../../api/services/jobService';
import type { machineService } from '../../../api/services/machineService';
import { JOB_ID, makeJob } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { JobsPage } from './JobsPage';

const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof jobService.list>(),
  transition: vi.fn<typeof jobService.transition>(),
  listMachines: vi.fn<typeof machineService.list>(),
}));
vi.mock('../../../api/services/jobService', () => ({
  jobService: { list: mocks.list, transition: mocks.transition },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: { list: mocks.listMachines },
}));

const READ = ['tenant.job.read'];
const WRITE = ['tenant.job.read', 'tenant.job.write'];
const APPROVE = ['tenant.job.read', 'tenant.job.approve'];
const page = (items = [makeJob({ status: 'APPROVED' })]) => ({
  items,
  total: items.length,
  page: 1,
  page_size: 25,
});

beforeEach(() => {
  mocks.list.mockResolvedValue(page());
  mocks.listMachines.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 });
});

async function openMenu(user: ReturnType<typeof userEvent.setup>) {
  const job = makeJob();
  await user.click(
    await screen.findByRole('button', { name: `Actions for job ${job.job_number}` }),
  );
}

describe('job list row actions', () => {
  it('hides Cancel without tenant.job.approve', async () => {
    const user = userEvent.setup();
    renderWithProviders(<JobsPage />, { tenantPermissions: READ });
    await openMenu(user);
    expect(screen.getByRole('menuitem', { name: 'View details' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Cancel job' })).not.toBeInTheDocument();
  });

  it('hides Cancel on jobs that can no longer be cancelled and mutes cancelled jobs', async () => {
    const user = userEvent.setup();
    mocks.list.mockResolvedValue(page([makeJob({ status: 'CANCELLED' })]));
    renderWithProviders(<JobsPage />, { tenantPermissions: APPROVE });
    expect((await screen.findByText(makeJob().job_number)).closest('tr')).toHaveAttribute(
      'data-muted',
      'true',
    );
    await openMenu(user);
    expect(screen.queryByRole('menuitem', { name: 'Cancel job' })).not.toBeInTheDocument();
  });

  it('cancels with a required reason via the CANCEL transition', async () => {
    const user = userEvent.setup();
    mocks.transition.mockResolvedValue(makeJob({ status: 'CANCELLED' }));
    renderWithProviders(<JobsPage />, { tenantPermissions: APPROVE });
    await openMenu(user);
    await user.click(screen.getByRole('menuitem', { name: 'Cancel job' }));
    await user.click(screen.getByRole('button', { name: 'Cancel job' }));
    expect(await screen.findByText('A reason is required')).toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Customer withdrew');
    await user.click(screen.getByRole('button', { name: 'Cancel job' }));
    await waitFor(() => {
      expect(mocks.transition).toHaveBeenCalledTimes(1);
    });
    const [id, body] = mocks.transition.mock.calls[0] ?? [];
    expect(id).toBe(JOB_ID);
    expect(body).toEqual({ action: 'CANCEL', reason: 'Customer withdrew' });
    await waitFor(() => {
      expect(mocks.list).toHaveBeenCalledTimes(2);
    });
  });

  it('shows the business error with its hint', async () => {
    const user = userEvent.setup();
    mocks.transition.mockRejectedValue(
      new ApiError({
        status: 409,
        code: 'INVALID_JOB_TRANSITION',
        message: 'Job is not cancellable.',
        correlationId: 'j1',
      }),
    );
    renderWithProviders(<JobsPage />, { tenantPermissions: APPROVE });
    await openMenu(user);
    await user.click(screen.getByRole('menuitem', { name: 'Cancel job' }));
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Scope cut');
    await user.click(screen.getByRole('button', { name: 'Cancel job' }));
    expect(
      await screen.findByText(/^INVALID_JOB_TRANSITION: Job is not cancellable\. — The job status/),
    ).toBeInTheDocument();
  });
});

describe('job edit gating', () => {
  it('offers Edit on draft jobs with tenant.job.write', async () => {
    const user = userEvent.setup();
    mocks.list.mockResolvedValue(page([makeJob({ status: 'DRAFT' })]));
    renderWithProviders(<JobsPage />, { tenantPermissions: WRITE });
    await openMenu(user);
    expect(screen.getByRole('menuitem', { name: 'Edit' })).toBeInTheDocument();
  });

  it('hides Edit on approved jobs and without tenant.job.write', async () => {
    const user = userEvent.setup();
    renderWithProviders(<JobsPage />, { tenantPermissions: WRITE });
    await openMenu(user);
    expect(screen.queryByRole('menuitem', { name: 'Edit' })).not.toBeInTheDocument();
  });

  it('hides Edit on draft jobs for read-only users', async () => {
    const user = userEvent.setup();
    mocks.list.mockResolvedValue(page([makeJob({ status: 'DRAFT' })]));
    renderWithProviders(<JobsPage />, { tenantPermissions: READ });
    await openMenu(user);
    expect(screen.queryByRole('menuitem', { name: 'Edit' })).not.toBeInTheDocument();
  });

  it('hides Edit while the tenant is READ_ONLY', async () => {
    const user = userEvent.setup();
    mocks.list.mockResolvedValue(page([makeJob({ status: 'DRAFT' })]));
    renderWithProviders(<JobsPage />, { tenantPermissions: WRITE, accessState: 'READ_ONLY' });
    await openMenu(user);
    expect(screen.queryByRole('menuitem', { name: 'Edit' })).not.toBeInTheDocument();
  });
});
