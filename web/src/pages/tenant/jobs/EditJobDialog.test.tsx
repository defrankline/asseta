import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { customerService } from '../../../api/services/customerService';
import type { jobService } from '../../../api/services/jobService';
import type { machineService } from '../../../api/services/machineService';
import type { staffService } from '../../../api/services/staffService';
import { STALE_RECORD_MESSAGE } from '../../../components/lifecycle/LifecycleActionDialog';
import { CONTRACT, JOB_ID, MACHINE, MACHINE_ID, makeJob } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { EditJobDialog } from './EditJobDialog';

const mocks = vi.hoisted(() => ({
  getContract: vi.fn<typeof customerService.getContract>(),
  listContracts: vi.fn<typeof customerService.listContracts>(),
  getMachine: vi.fn<typeof machineService.get>(),
  listMachines: vi.fn<typeof machineService.list>(),
  getStaff: vi.fn<typeof staffService.get>(),
  listStaff: vi.fn<typeof staffService.list>(),
  update: vi.fn<typeof jobService.update>(),
}));
vi.mock('../../../api/services/customerService', () => ({
  customerService: { getContract: mocks.getContract, listContracts: mocks.listContracts },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: { get: mocks.getMachine, list: mocks.listMachines },
}));
vi.mock('../../../api/services/staffService', () => ({
  staffService: { get: mocks.getStaff, list: mocks.listStaff },
}));
vi.mock('../../../api/services/jobService', () => ({ jobService: { update: mocks.update } }));

const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 20 });
const JOB = makeJob({ status: 'PENDING_APPROVAL', version: 4 });

beforeEach(() => {
  mocks.getContract.mockResolvedValue(CONTRACT);
  mocks.getMachine.mockResolvedValue(MACHINE);
  mocks.listMachines.mockResolvedValue(page([MACHINE]));
  mocks.listStaff.mockResolvedValue(page([]));
});

type User = ReturnType<typeof userEvent.setup>;

function render(onReloadRequested = vi.fn(), onSaved = vi.fn()) {
  renderWithProviders(
    <EditJobDialog
      job={JOB}
      timeZone="UTC"
      onClose={vi.fn()}
      onSaved={onSaved}
      onReloadRequested={onReloadRequested}
    />,
    { tenantPermissions: ['tenant.job.read', 'tenant.job.write'] },
  );
  return { onReloadRequested, onSaved };
}

async function toReviewAndSave(user: User) {
  await waitFor(() => {
    expect(screen.getByRole('combobox', { name: /^Machine/ })).toHaveValue('EX-01 · Excavator');
  });
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByText('Schedule', { selector: '.Mui-active' });
  await user.click(screen.getByRole('button', { name: 'Next' }));
  expect(await screen.findByRole('textbox', { name: /Negotiated hourly rate/ })).toHaveValue(
    '150000.0000',
  );
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await user.click(await screen.findByRole('button', { name: 'Save changes' }));
}

describe('EditJobDialog', () => {
  it('prefills the job with contract and job number fixed', async () => {
    render();
    expect(await screen.findByRole('textbox', { name: 'Contract' })).toHaveValue('C-1');
    expect(screen.getByRole('textbox', { name: 'Contract' })).toBeDisabled();
    expect(screen.getByRole('textbox', { name: 'Job number' })).toHaveValue('J-100');
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /^Machine/ })).toHaveValue('EX-01 · Excavator');
    });
  });

  it('submits the terms with the version that was read', async () => {
    const user = userEvent.setup();
    const saved = makeJob({ status: 'PENDING_APPROVAL', version: 5 });
    mocks.update.mockResolvedValue(saved);
    const { onSaved } = render();
    await toReviewAndSave(user);
    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledTimes(1);
    });
    const [id, body] = mocks.update.mock.calls[0] ?? [];
    expect(id).toBe(JOB_ID);
    expect(body).toMatchObject({
      machine_id: MACHINE_ID,
      hourly_rate: '150000.0000',
      planned_start: JOB.planned_start,
      version: 4,
    });
    expect(body).not.toHaveProperty('contract_id');
    expect(body).not.toHaveProperty('job_number');
    expect(onSaved).toHaveBeenCalledWith(saved);
  });

  it('offers Reload on STALE_VERSION', async () => {
    const user = userEvent.setup();
    mocks.update.mockRejectedValue(
      new ApiError({ status: 409, code: 'STALE_VERSION', message: 'Stale', correlationId: 'c' }),
    );
    const { onReloadRequested } = render();
    await toReviewAndSave(user);
    expect(await screen.findByText(STALE_RECORD_MESSAGE)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reload' }));
    expect(onReloadRequested).toHaveBeenCalledTimes(1);
  });

  it('explains JOB_LOCKED', async () => {
    const user = userEvent.setup();
    mocks.update.mockRejectedValue(
      new ApiError({
        status: 422,
        code: 'JOB_LOCKED',
        message: 'Job is locked.',
        correlationId: 'l',
      }),
    );
    render();
    await toReviewAndSave(user);
    expect(
      await screen.findByText(/^JOB_LOCKED: Job is locked\. — Approved, running and finished/),
    ).toBeInTheDocument();
  });
});
