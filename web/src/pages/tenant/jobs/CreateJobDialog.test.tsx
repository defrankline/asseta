import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { customerService } from '../../../api/services/customerService';
import type { jobService } from '../../../api/services/jobService';
import type { machineService } from '../../../api/services/machineService';
import type { staffService } from '../../../api/services/staffService';
import { CONTRACT, MACHINE, makeJob } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { CreateJobDialog } from './CreateJobDialog';

const mocks = vi.hoisted(() => ({
  listContracts: vi.fn<typeof customerService.listContracts>(),
  listMachines: vi.fn<typeof machineService.list>(),
  listStaff: vi.fn<typeof staffService.list>(),
  create: vi.fn<typeof jobService.create>(),
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

const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 20 });

beforeEach(() => {
  mocks.listContracts.mockResolvedValue(page([CONTRACT]));
  mocks.listMachines.mockResolvedValue(page([MACHINE]));
  mocks.listStaff.mockResolvedValue(page([]));
  mocks.create.mockResolvedValue(makeJob());
});

type User = ReturnType<typeof userEvent.setup>;

async function fillAssignment(user: User) {
  await user.click(screen.getByRole('combobox', { name: /^Contract/ }));
  await user.click(await screen.findByRole('option', { name: 'C-1' }));
  await user.type(screen.getByRole('textbox', { name: /Job number/ }), 'J-7');
  await user.click(screen.getByRole('combobox', { name: /^Machine/ }));
  await user.click(await screen.findByRole('option', { name: 'EX-01 · Excavator' }));
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByText('Schedule', { selector: '.Mui-active' });
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByText('Hourly rate source');
}

async function choose(user: User, label: RegExp, option: string) {
  await user.click(screen.getByRole('combobox', { name: label }));
  await user.click(await screen.findByRole('option', { name: option }));
}

function render() {
  renderWithProviders(<CreateJobDialog timeZone="UTC" onClose={vi.fn()} onCreated={vi.fn()} />, {
    tenantPermissions: ['tenant.job.read', 'tenant.job.write'],
  });
}

describe('CreateJobDialog', () => {
  it('omits the hourly rate when the rate card is used and says so on Review', async () => {
    const user = userEvent.setup();
    render();
    await fillAssignment(user);
    await user.click(screen.getByRole('button', { name: 'Next' }));
    const review = await screen.findByText(/Rate source:/);
    expect(within(review).getByText('Tenant rate card')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Create job' }));
    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledTimes(1);
    });
    expect(mocks.create.mock.calls[0]?.[0]).toMatchObject({
      contract_id: CONTRACT.id,
      machine_id: MACHINE.id,
      job_number: 'J-7',
      hourly_rate: null,
      minimum_hours: null,
      standby_treatment: 'EXCLUDED',
      standby_rate: null,
      mobilization_fee: '0',
      discount_percent: '0',
      tax_rate_percent: '0',
    });
  });

  it('requires a negotiated rate and a standby rate for STANDBY_RATE, sent as strings', async () => {
    const user = userEvent.setup();
    render();
    await fillAssignment(user);
    await user.click(screen.getByRole('radio', { name: 'Negotiated rate' }));
    await choose(user, /Standby treatment/, 'Separate standby rate');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Enter the negotiated hourly rate')).toBeInTheDocument();
    expect(screen.getByText('Enter the standby rate')).toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: /Negotiated hourly rate/ }), '1500.50');
    await user.type(screen.getByRole('textbox', { name: /Standby rate/ }), '200');
    await user.clear(screen.getByRole('textbox', { name: /Minimum hours/ }));
    await user.type(screen.getByRole('textbox', { name: /Minimum hours/ }), '4');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    const review = await screen.findByText(/Rate source:/);
    expect(within(review).getByText('Negotiated')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Create job' }));
    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledTimes(1);
    });
    expect(mocks.create.mock.calls[0]?.[0]).toMatchObject({
      hourly_rate: '1500.50',
      minimum_hours: '4',
      standby_treatment: 'STANDBY_RATE',
      standby_rate: '200',
    });
  });

  it('drops a typed standby rate when standby is no longer a separate rate', async () => {
    const user = userEvent.setup();
    render();
    await fillAssignment(user);
    await choose(user, /Standby treatment/, 'Separate standby rate');
    await user.type(screen.getByRole('textbox', { name: /Standby rate/ }), '200');
    await choose(user, /Standby treatment/, 'Included (billed at the hourly rate)');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Create job' }));
    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledTimes(1);
    });
    expect(mocks.create.mock.calls[0]?.[0]).toMatchObject({
      hourly_rate: null,
      standby_treatment: 'INCLUDED',
      standby_rate: null,
    });
  });
});
