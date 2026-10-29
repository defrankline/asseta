import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { machineService } from '../../../api/services/machineService';
import { STALE_RECORD_MESSAGE } from '../../../components/lifecycle/LifecycleActionDialog';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { MachineDetailPage } from '../machineDetail/MachineDetailPage';
import { makeMachine } from './machineFixtures';
import { MachinesPage } from './MachinesPage';

const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof machineService.list>(),
  get: vi.fn<typeof machineService.get>(),
  update: vi.fn<typeof machineService.update>(),
  listCategories: vi.fn<typeof machineService.listCategories>(),
  listAreas: vi.fn<typeof machineService.listAreas>(),
  deactivate: vi.fn<typeof machineService.deactivate>(),
  reactivate: vi.fn<typeof machineService.reactivate>(),
}));
vi.mock('../../../api/services/machineService', () => ({ machineService: mocks }));
const trackers = vi.hoisted(() => ({ list: vi.fn() }));
vi.mock('../../../api/services/trackerService', () => ({ trackerService: trackers }));

const READ = ['tenant.machine.read'];
const WRITE = ['tenant.machine.read', 'tenant.machine.write'];
const MENU = 'Actions for EX-01 · Excavator 1';
const page = (items = [makeMachine()]) => ({ items, total: items.length, page: 1, page_size: 25 });

beforeEach(() => {
  mocks.list.mockResolvedValue(page());
  mocks.get.mockResolvedValue(makeMachine());
  mocks.listCategories.mockResolvedValue([]);
  mocks.listAreas.mockResolvedValue([]);
});

async function openMenuItem(user: ReturnType<typeof userEvent.setup>, item: string) {
  await user.click(await screen.findByRole('button', { name: MENU }));
  await user.click(screen.getByRole('menuitem', { name: item }));
}

describe('machine list ?missing= views (go-live checklist links)', () => {
  it('?missing=tracker lists only active machines without a current main tracker', async () => {
    const fitted = makeMachine({ id: 'm-fitted', asset_code: 'EX-02', name: 'Excavator 2' });
    mocks.list.mockResolvedValue(page([makeMachine(), fitted]));
    trackers.list.mockResolvedValue({
      items: [
        {
          id: 't-1',
          current_assignment: {
            id: 'a-1',
            tracker_id: 't-1',
            machine_id: 'm-fitted',
            is_primary: true,
            effective_from: '2026-10-01T00:00:00Z',
            effective_to: null,
            reason: null,
          },
        },
      ],
      total: 1,
      page: 1,
      page_size: 200,
    });
    renderWithProviders(<MachinesPage />, {
      tenantPermissions: READ,
      route: '/tenant/machines?missing=tracker',
    });
    expect(await screen.findByText('Excavator 1')).toBeInTheDocument();
    expect(screen.queryByText('Excavator 2')).not.toBeInTheDocument();
    expect(screen.getByText(/do not have a main tracker fitted yet/)).toBeInTheDocument();
    expect(mocks.list.mock.calls[0]?.[0]).toMatchObject({
      page: 1,
      page_size: 200,
      filters: { status: 'ACTIVE' },
    });
  });

  it('?missing=enrollment lists active machines with how to enrol them; Show all clears it', async () => {
    const user = userEvent.setup();
    renderWithProviders(<MachinesPage />, {
      tenantPermissions: READ,
      route: '/tenant/machines?missing=enrollment',
    });
    expect(await screen.findByText('Excavator 1')).toBeInTheDocument();
    expect(screen.getByText(/Enroll as billable asset/)).toBeInTheDocument();
    expect(mocks.list.mock.calls[0]?.[0].filters).toEqual({ status: 'ACTIVE' });
    await user.click(screen.getByRole('button', { name: 'Show all machines' }));
    expect(screen.queryByText(/Enroll as billable asset/)).not.toBeInTheDocument();
  });
});

describe('machine list row actions', () => {
  it('opens Edit prefilled from the list and saves with the version that was read', async () => {
    const user = userEvent.setup();
    mocks.update.mockResolvedValue(makeMachine({ version: 4, name: 'Excavator X' }));
    renderWithProviders(<MachinesPage />, { tenantPermissions: WRITE });
    await openMenuItem(user, 'Edit');
    const name = await screen.findByRole('textbox', { name: /^Name/ });
    expect(name).toHaveValue('Excavator 1');
    await user.clear(name);
    await user.type(name, 'Excavator X');
    for (let i = 0; i < 3; i += 1) await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Save changes' }));
    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledTimes(1);
    });
    expect(mocks.update.mock.calls[0]?.[1]).toMatchObject({ name: 'Excavator X', version: 3 });
    await waitFor(() => {
      expect(mocks.list).toHaveBeenCalledTimes(2);
    });
  });

  it('takes a machine out of service with the full record and version', async () => {
    const user = userEvent.setup();
    mocks.update.mockResolvedValue(makeMachine({ status: 'OUT_OF_SERVICE', version: 4 }));
    renderWithProviders(<MachinesPage />, { tenantPermissions: WRITE });
    await openMenuItem(user, 'Take out of service');
    expect(screen.getByText(/stays in the registry with all of its history/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Take out of service' }));
    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledTimes(1);
    });
    const [id, body, key] = mocks.update.mock.calls[0] ?? [];
    expect(id).toBe(makeMachine().id);
    expect(body).toMatchObject({ status: 'OUT_OF_SERVICE', version: 3, name: 'Excavator 1' });
    expect(typeof key).toBe('string');
    expect(await screen.findByText('EX-01 · Excavator 1 is now out of service.')).toBeVisible();
  });

  it('retires with a required reason and the version via deactivate', async () => {
    const user = userEvent.setup();
    mocks.deactivate.mockResolvedValue(makeMachine({ status: 'DISPOSED', version: 4 }));
    renderWithProviders(<MachinesPage />, { tenantPermissions: WRITE });
    await openMenuItem(user, 'Retire (dispose)');
    expect(screen.getByText(/It becomes Disposed/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retire' }));
    expect(await screen.findByText('A reason is required')).toBeInTheDocument();
    expect(mocks.deactivate).not.toHaveBeenCalled();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Sold at auction');
    await user.click(screen.getByRole('button', { name: 'Retire' }));
    await waitFor(() => {
      expect(mocks.deactivate).toHaveBeenCalledTimes(1);
    });
    expect(mocks.deactivate.mock.calls[0]?.slice(0, 2)).toEqual([
      makeMachine().id,
      { reason: 'Sold at auction', version: 3 },
    ]);
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it('shows a server business error in the dialog', async () => {
    const user = userEvent.setup();
    mocks.deactivate.mockRejectedValue(
      new ApiError({
        status: 422,
        code: 'MACHINE_HAS_OPEN_JOBS',
        message: 'The machine has open jobs.',
        correlationId: 'r1',
      }),
    );
    renderWithProviders(<MachinesPage />, { tenantPermissions: WRITE });
    await openMenuItem(user, 'Retire (dispose)');
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Sold');
    await user.click(screen.getByRole('button', { name: 'Retire' }));
    expect(
      await screen.findByText(
        /^MACHINE_HAS_OPEN_JOBS: The machine has open jobs\. — Complete or cancel the open jobs/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('reinstates a retired machine with a reason', async () => {
    const user = userEvent.setup();
    mocks.list.mockResolvedValue(page([makeMachine({ status: 'DISPOSED' })]));
    mocks.reactivate.mockResolvedValue(makeMachine({ version: 5 }));
    renderWithProviders(<MachinesPage />, { tenantPermissions: WRITE });
    await openMenuItem(user, 'Reinstate');
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Bought back');
    await user.click(screen.getByRole('button', { name: 'Reinstate' }));
    await waitFor(() => {
      expect(mocks.reactivate.mock.calls[0]?.[1]).toEqual({ reason: 'Bought back', version: 3 });
    });
  });

  it('sends include_inactive only when Show retired is on', async () => {
    const user = userEvent.setup();
    renderWithProviders(<MachinesPage />, { tenantPermissions: READ });
    expect(await screen.findByText('EX-01')).toBeInTheDocument();
    expect(mocks.list.mock.calls[0]?.[0].filters?.include_inactive).toBeUndefined();
    await user.click(screen.getByRole('switch', { name: 'Show retired' }));
    await waitFor(() => {
      expect(mocks.list.mock.lastCall?.[0].filters).toMatchObject({ include_inactive: 'true' });
    });
  });

  it('offers Reload on STALE_VERSION and refetches the list', async () => {
    const user = userEvent.setup();
    mocks.update.mockRejectedValue(
      new ApiError({ status: 409, code: 'STALE_VERSION', message: 'Stale', correlationId: 'r2' }),
    );
    renderWithProviders(<MachinesPage />, { tenantPermissions: WRITE });
    await openMenuItem(user, 'Take out of service');
    await user.click(screen.getByRole('button', { name: 'Take out of service' }));
    expect(await screen.findByText(STALE_RECORD_MESSAGE)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reload' }));
    await waitFor(() => {
      expect(mocks.list).toHaveBeenCalledTimes(2);
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('mutes disposed machines and offers no edits on them', async () => {
    const user = userEvent.setup();
    mocks.list.mockResolvedValue(page([makeMachine({ status: 'DISPOSED' })]));
    renderWithProviders(<MachinesPage />, { tenantPermissions: WRITE });
    expect((await screen.findByText('EX-01')).closest('tr')).toHaveAttribute('data-muted', 'true');
    await user.click(screen.getByRole('button', { name: MENU }));
    expect(screen.getByRole('menuitem', { name: 'View details' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: /Retire/ })).not.toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Reinstate' })).toBeInTheDocument();
  });

  it('returns an out-of-service machine to service', async () => {
    const user = userEvent.setup();
    mocks.list.mockResolvedValue(page([makeMachine({ status: 'OUT_OF_SERVICE' })]));
    mocks.update.mockResolvedValue(makeMachine({ status: 'ACTIVE', version: 4 }));
    renderWithProviders(<MachinesPage />, { tenantPermissions: WRITE });
    await openMenuItem(user, 'Return to service');
    await user.click(screen.getByRole('button', { name: 'Return to service' }));
    await waitFor(() => {
      expect(mocks.update.mock.calls[0]?.[1]).toMatchObject({ status: 'ACTIVE', version: 3 });
    });
  });
});

describe('machine details page actions', () => {
  it('hides Edit and status changes without tenant.machine.write', async () => {
    renderWithProviders(<MachineDetailPage />, { tenantPermissions: READ });
    expect(await screen.findByText('Registry record')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Retire (dispose)' })).not.toBeInTheDocument();
  });

  it('shows Edit and status changes with tenant.machine.write', async () => {
    renderWithProviders(<MachineDetailPage />, { tenantPermissions: WRITE });
    expect(await screen.findByRole('button', { name: 'Edit' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Take out of service' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retire (dispose)' })).toBeInTheDocument();
  });

  it('shows the retired banner with its reason and no edits on a disposed machine', async () => {
    mocks.get.mockResolvedValue(
      makeMachine({ status: 'DISPOSED', deactivation_reason: 'Sold at auction' }),
    );
    renderWithProviders(<MachineDetailPage />, { tenantPermissions: WRITE });
    expect(await screen.findByText(/This machine is retired/)).toBeInTheDocument();
    // The inactive banner is a status region; a still-loading section may be another one on slow runners.
    expect(screen.getByText(/Reason: Sold at auction/).closest('[role="status"]')).not.toBeNull();
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reinstate' })).toBeInTheDocument();
  });
});
