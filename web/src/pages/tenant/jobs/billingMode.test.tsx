import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { customerService } from '../../../api/services/customerService';
import type { jobService } from '../../../api/services/jobService';
import type { machineService } from '../../../api/services/machineService';
import type { policyService } from '../../../api/services/policyService';
import type { staffService } from '../../../api/services/staffService';
import { CONTRACT, MACHINE, makeJob } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { CreateJobDialog } from './CreateJobDialog';

const mocks = vi.hoisted(() => ({
  listContracts: vi.fn<typeof customerService.listContracts>(),
  listMachines: vi.fn<typeof machineService.list>(),
  listStaff: vi.fn<typeof staffService.list>(),
  create: vi.fn<typeof jobService.create>(),
  effective: vi.fn<typeof policyService.effective>(),
}));
vi.mock('../../../api/services/customerService', () => ({
  customerService: { listContracts: mocks.listContracts },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: { list: mocks.listMachines },
}));
vi.mock('../../../api/services/staffService', () => ({
  staffService: { list: mocks.listStaff },
}));
vi.mock('../../../api/services/jobService', () => ({ jobService: { create: mocks.create } }));
vi.mock('../../../api/services/policyService', () => ({
  policyService: { effective: mocks.effective },
}));

const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 20 });
const HOURS = {
  enabled: true,
  billing_modes: ['INVOICE', 'PREPAID_HOURS'],
  default_billing_mode: 'INVOICE',
};

beforeEach(() => {
  mocks.listContracts.mockResolvedValue(page([CONTRACT]));
  mocks.listMachines.mockResolvedValue(page([MACHINE]));
  mocks.listStaff.mockResolvedValue(page([]));
  mocks.create.mockResolvedValue(makeJob());
});

async function toPricing(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('combobox', { name: /^Contract/ }));
  await user.click(await screen.findByRole('option', { name: 'C-1' }));
  await user.type(screen.getByRole('textbox', { name: /Job number/ }), 'J-8');
  await user.click(screen.getByRole('combobox', { name: /^Machine/ }));
  await user.click(await screen.findByRole('option', { name: 'EX-01 · Excavator' }));
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByText('Schedule', { selector: '.Mui-active' });
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByText('Hourly rate source');
}

function render(policyRead: boolean) {
  renderWithProviders(<CreateJobDialog timeZone="UTC" onClose={vi.fn()} onCreated={vi.fn()} />, {
    tenantPermissions: [
      'tenant.job.read',
      'tenant.job.write',
      ...(policyRead ? ['tenant.policy.read'] : []),
    ],
  });
}

describe('job billing mode', () => {
  it('offers the policy billing modes and sends the chosen one', async () => {
    const user = userEvent.setup();
    mocks.effective.mockResolvedValue({
      policy_type: 'CUSTOMER_HOURS',
      version_stamp: 'v1',
      values: HOURS,
    });
    render(true);
    await toPricing(user);
    await user.click(await screen.findByRole('combobox', { name: /^Billing/ }));
    expect(
      screen.getByRole('option', { name: 'Company default (Invoice after the work)' }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('option', { name: 'Prepaid customer hours' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Create job' }));
    await waitFor(() => {
      expect(mocks.create.mock.calls[0]?.[0]).toMatchObject({ billing_mode: 'PREPAID_HOURS' });
    });
  });

  it('shows no billing choice when customer hours are off', async () => {
    const user = userEvent.setup();
    mocks.effective.mockResolvedValue({
      policy_type: 'CUSTOMER_HOURS',
      version_stamp: 'v1',
      values: { ...HOURS, enabled: false },
    });
    render(true);
    await toPricing(user);
    expect(screen.queryByRole('combobox', { name: /^Billing/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Create job' }));
    await waitFor(() => {
      expect(mocks.create.mock.calls[0]?.[0]).toMatchObject({ billing_mode: null });
    });
  });
});
