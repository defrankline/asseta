import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { machineService } from '../../../api/services/machineService';
import type { trackerService } from '../../../api/services/trackerService';
import { STALE_RECORD_MESSAGE } from '../../../components/lifecycle/LifecycleActionDialog';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { MACHINE, MACHINE_ID, makeTracker, TRACKER_ID } from './trackerFixtures';
import { TrackerDetailPage } from './TrackerDetailPage';
import { TrackersPage } from './TrackersPage';

const mocks = vi.hoisted(() => ({
  get: vi.fn<typeof trackerService.get>(),
  list: vi.fn<typeof trackerService.list>(),
  changeState: vi.fn<typeof trackerService.changeState>(),
  update: vi.fn<typeof trackerService.update>(),
  listIngestionEvents: vi.fn<typeof trackerService.listIngestionEvents>(),
  listMachines: vi.fn<typeof machineService.list>(),
  getMachine: vi.fn<typeof machineService.get>(),
  listTrackerAssignments: vi.fn<typeof machineService.listTrackerAssignments>(),
}));
vi.mock('../../../api/services/trackerService', () => ({
  trackerService: {
    get: mocks.get,
    list: mocks.list,
    changeState: mocks.changeState,
    update: mocks.update,
    listIngestionEvents: mocks.listIngestionEvents,
  },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: {
    list: mocks.listMachines,
    get: mocks.getMachine,
    listTrackerAssignments: mocks.listTrackerAssignments,
  },
}));

const READ = ['tenant.tracker.read', 'tenant.machine.read'];
const WRITE = [...READ, 'tenant.tracker.write'];
const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 25 });
const ASSIGNMENT = {
  id: 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
  tracker_id: TRACKER_ID,
  machine_id: MACHINE_ID,
  is_primary: true,
  effective_from: '2026-10-01T00:00:00Z',
  effective_to: null,
  reason: 'Fitted',
};

beforeEach(() => {
  mocks.get.mockResolvedValue(makeTracker());
  mocks.list.mockResolvedValue(page([makeTracker()]));
  mocks.listIngestionEvents.mockResolvedValue(page([]));
  mocks.listMachines.mockResolvedValue(page([MACHINE]));
  mocks.getMachine.mockResolvedValue(MACHINE);
  mocks.listTrackerAssignments.mockResolvedValue([]);
});

describe('tracker details page', () => {
  it('shows the device, its machine and its assignment history on that machine', async () => {
    mocks.get.mockResolvedValue(makeTracker({ current_assignment: ASSIGNMENT }));
    mocks.listTrackerAssignments.mockResolvedValue([
      ASSIGNMENT,
      { ...ASSIGNMENT, id: 'old', effective_to: '2026-09-01T00:00:00Z', reason: 'Earlier' },
      { ...ASSIGNMENT, id: 'other', tracker_id: 'someone-else', reason: 'Other tracker' },
    ]);
    renderWithProviders(<TrackerDetailPage />, { tenantPermissions: READ });
    expect(await screen.findByRole('heading', { name: 'Tracker TRK-01' })).toBeInTheDocument();
    expect(screen.getByText('356938035643809')).toBeInTheDocument();
    expect(await screen.findByRole('link', { name: 'EX-01 · Excavator' })).toBeInTheDocument();
    expect(await screen.findByText('Earlier')).toBeInTheDocument();
    expect(screen.queryByText('Other tracker')).not.toBeInTheDocument();
  });

  it('retires a tracker only with a reason and sends RETIRED with it', async () => {
    const user = userEvent.setup();
    mocks.changeState.mockResolvedValue(makeTracker({ provisioning_state: 'RETIRED' }));
    renderWithProviders(<TrackerDetailPage />, { tenantPermissions: WRITE });
    await user.click(await screen.findByRole('button', { name: 'Retire (decommission)' }));
    expect(screen.getByText(/Retirement is permanent/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retire tracker' }));
    expect(await screen.findByText('A reason is required')).toBeInTheDocument();
    expect(mocks.changeState).not.toHaveBeenCalled();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Water damage');
    await user.click(screen.getByRole('button', { name: 'Retire tracker' }));
    await waitFor(() => {
      expect(mocks.changeState).toHaveBeenCalledTimes(1);
    });
    const [id, body] = mocks.changeState.mock.calls[0] ?? [];
    expect(id).toBe(TRACKER_ID);
    expect(body).toEqual({ state: 'RETIRED', reason: 'Water damage' });
    await waitFor(() => {
      expect(mocks.get).toHaveBeenCalledTimes(2);
    });
  });

  it('reactivates a suspended tracker', async () => {
    const user = userEvent.setup();
    mocks.get.mockResolvedValue(makeTracker({ provisioning_state: 'SUSPENDED' }));
    mocks.changeState.mockResolvedValue(makeTracker({ provisioning_state: 'REGISTERED' }));
    renderWithProviders(<TrackerDetailPage />, { tenantPermissions: WRITE });
    expect(await screen.findByText(/suspended: its data is quarantined/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Suspend' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reactivate' }));
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'SIM topped up');
    await user.click(screen.getByRole('button', { name: 'Reactivate' }));
    await waitFor(() => {
      expect(mocks.changeState.mock.calls[0]?.[1]).toEqual({
        state: 'REGISTERED',
        reason: 'SIM topped up',
      });
    });
  });

  it('keeps the dialog open with the server error', async () => {
    const user = userEvent.setup();
    mocks.changeState.mockRejectedValue(
      new ApiError({
        status: 409,
        code: 'INVALID_STATE_TRANSITION',
        message: 'Not allowed from this state.',
        correlationId: 'x1',
      }),
    );
    renderWithProviders(<TrackerDetailPage />, { tenantPermissions: WRITE });
    await user.click(await screen.findByRole('button', { name: 'Suspend' }));
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Lost');
    await user.click(screen.getByRole('button', { name: 'Suspend' }));
    expect(
      await screen.findByText(/^INVALID_STATE_TRANSITION: Not allowed from this state\./),
    ).toBeInTheDocument();
    expect(screen.queryByText(STALE_RECORD_MESSAGE)).not.toBeInTheDocument();
  });

  it('shows no lifecycle actions on a retired tracker', async () => {
    mocks.get.mockResolvedValue(makeTracker({ provisioning_state: 'RETIRED' }));
    renderWithProviders(<TrackerDetailPage />, { tenantPermissions: WRITE });
    expect(await screen.findByText(/This tracker is retired/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Assign / swap' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reactivate' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
  });
});

describe('tracker list row actions', () => {
  it('offers only View details without tenant.tracker.write', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TrackersPage />, { tenantPermissions: READ });
    await user.click(await screen.findByRole('button', { name: 'Actions for tracker TRK-01' }));
    expect(screen.getByRole('menuitem', { name: 'View details' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Suspend' })).not.toBeInTheDocument();
  });

  it('mutes retired trackers and suspends from the row menu', async () => {
    const user = userEvent.setup();
    mocks.list.mockResolvedValue(
      page([
        makeTracker(),
        makeTracker({ id: 'retired-1', label: 'TRK-OLD', provisioning_state: 'RETIRED' }),
      ]),
    );
    mocks.changeState.mockResolvedValue(makeTracker({ provisioning_state: 'SUSPENDED' }));
    renderWithProviders(<TrackersPage />, { tenantPermissions: WRITE });
    expect((await screen.findByText('TRK-OLD')).closest('tr')).toHaveAttribute(
      'data-muted',
      'true',
    );
    await user.click(screen.getByRole('button', { name: 'Actions for tracker TRK-01' }));
    await user.click(screen.getByRole('menuitem', { name: 'Suspend' }));
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Vehicle parked');
    await user.click(screen.getByRole('button', { name: 'Suspend' }));
    await waitFor(() => {
      expect(mocks.changeState.mock.calls[0]?.[1]).toEqual({
        state: 'SUSPENDED',
        reason: 'Vehicle parked',
      });
    });
    await waitFor(() => {
      expect(mocks.list).toHaveBeenCalledTimes(2);
    });
  });
});

describe('tracker edit', () => {
  async function editAndSave(user: ReturnType<typeof userEvent.setup>) {
    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    const label = await screen.findByRole('textbox', { name: /^Label/ });
    expect(label).toHaveValue('TRK-01');
    await user.clear(label);
    await user.type(label, 'Excavator unit');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByRole('textbox', { name: 'SIM MSISDN' })).toHaveValue('+255700000001');
    expect(screen.getByRole('textbox', { name: 'Carrier' })).toHaveValue('Vodacom');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Save changes' }));
  }

  it('is hidden without tenant.tracker.write', async () => {
    renderWithProviders(<TrackerDetailPage />, { tenantPermissions: READ });
    expect(await screen.findByRole('region', { name: 'Device' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
  });

  it('saves label, SIM and carrier with the version that was read', async () => {
    const user = userEvent.setup();
    mocks.get.mockResolvedValue(makeTracker({ version: 5 }));
    mocks.update.mockResolvedValue(makeTracker({ label: 'Excavator unit', version: 6 }));
    renderWithProviders(<TrackerDetailPage />, { tenantPermissions: WRITE });
    await editAndSave(user);
    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledTimes(1);
    });
    const [id, body] = mocks.update.mock.calls[0] ?? [];
    expect(id).toBe(TRACKER_ID);
    expect(body).toEqual({
      label: 'Excavator unit',
      sim_iccid: null,
      sim_msisdn: '+255700000001',
      carrier: 'Vodacom',
      version: 5,
    });
    await waitFor(() => {
      expect(mocks.get).toHaveBeenCalledTimes(2);
    });
  });

  it('offers Reload on STALE_VERSION', async () => {
    const user = userEvent.setup();
    mocks.update.mockRejectedValue(
      new ApiError({ status: 409, code: 'STALE_VERSION', message: 'Stale', correlationId: 's' }),
    );
    renderWithProviders(<TrackerDetailPage />, { tenantPermissions: WRITE });
    await editAndSave(user);
    expect(await screen.findByText(STALE_RECORD_MESSAGE)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reload' }));
    await waitFor(() => {
      expect(mocks.get).toHaveBeenCalledTimes(2);
    });
  });

  it('sends include_inactive when Show retired is on', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TrackersPage />, { tenantPermissions: READ });
    await screen.findByText('TRK-01');
    expect(mocks.list.mock.calls[0]?.[0].filters).toEqual({
      state: undefined,
      include_inactive: undefined,
    });
    await user.click(screen.getByRole('switch', { name: 'Show retired' }));
    await waitFor(() => {
      expect(mocks.list.mock.lastCall?.[0].filters).toEqual({
        state: undefined,
        include_inactive: 'true',
      });
    });
  });
});
