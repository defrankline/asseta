import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { machineService } from '../../../api/services/machineService';
import type { trackerService } from '../../../api/services/trackerService';
import type { TrackerAssignmentDto } from '../../../api/types';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { AssignTrackerDialog, SWAP_WARNING } from './AssignTrackerDialog';
import { IngestionEventsPanel } from './IngestionEventsPanel';
import { MACHINE, MACHINE_ID, makeTracker, TRACKER_ID } from './trackerFixtures';
import { TrackerDrawer } from './TrackerDrawer';
import { TrackersPage } from './TrackersPage';

const mocks = vi.hoisted(() => ({
  get: vi.fn<typeof trackerService.get>(),
  list: vi.fn<typeof trackerService.list>(),
  assign: vi.fn<typeof trackerService.assign>(),
  listIngestionEvents: vi.fn<typeof trackerService.listIngestionEvents>(),
  listMachines: vi.fn<typeof machineService.list>(),
}));
vi.mock('../../../api/services/trackerService', () => ({
  trackerService: {
    get: mocks.get,
    list: mocks.list,
    assign: mocks.assign,
    listIngestionEvents: mocks.listIngestionEvents,
  },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: { list: mocks.listMachines },
}));

const READ = [P.tenantTrackerRead];
const WRITE = [P.tenantTrackerRead, P.tenantTrackerWrite];
const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 25 });

function renderDrawer(perms: string[]) {
  return renderWithProviders(
    <TrackerDrawer
      trackerId={TRACKER_ID}
      onClose={vi.fn()}
      onChanged={vi.fn()}
      onViewEvents={vi.fn()}
    />,
    { tenantPermissions: perms },
  );
}

describe('tracker capability matrix', () => {
  it('distinguishes declared from verified capabilities', async () => {
    mocks.get.mockResolvedValue(makeTracker());
    renderDrawer(READ);
    expect(await screen.findByText(/Declared ≠ verified/)).toBeInTheDocument();
    const gnss = screen.getByTestId('capability-GNSS');
    expect(within(gnss).getByText(/^Verified 1 Oct 2026/)).toBeInTheDocument();
    const ignition = screen.getByTestId('capability-IGNITION');
    expect(within(ignition).getByText('Yes')).toBeInTheDocument();
    expect(within(ignition).getByText('Declared only · not verified')).toBeInTheDocument();
    expect(within(ignition).queryByText(/^Verified/)).not.toBeInTheDocument();
  });
});

describe('tracker write actions are permission gated', () => {
  it('hides assign / unassign / state change without tenant.tracker.write', async () => {
    mocks.get.mockResolvedValue(
      makeTracker({
        current_assignment: {
          id: 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
          tracker_id: TRACKER_ID,
          machine_id: MACHINE_ID,
          is_primary: true,
          effective_from: '2026-10-01T00:00:00Z',
          effective_to: null,
          reason: null,
        },
      }),
    );
    const { unmount } = renderDrawer(READ);
    expect(
      await screen.findByRole('button', { name: 'View ingestion events' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Assign / swap' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Unassign' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Change state' })).not.toBeInTheDocument();
    unmount();
    renderDrawer(WRITE);
    expect(await screen.findByRole('button', { name: 'Assign / swap' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Unassign' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Change state' })).toBeInTheDocument();
  });

  it('shows "Register tracker" only with tenant.tracker.write', async () => {
    mocks.list.mockResolvedValue(page([]));
    const { unmount } = renderWithProviders(<TrackersPage />, { tenantPermissions: READ });
    expect(await screen.findByText('No trackers registered')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Register tracker' })).not.toBeInTheDocument();
    unmount();
    renderWithProviders(<TrackersPage />, { tenantPermissions: WRITE });
    expect(await screen.findByRole('button', { name: 'Register tracker' })).toBeInTheDocument();
  });

  it('hides write actions while the tenant is READ_ONLY', async () => {
    mocks.list.mockResolvedValue(page([]));
    renderWithProviders(<TrackersPage />, { tenantPermissions: WRITE, accessState: 'READ_ONLY' });
    expect(await screen.findByText('No trackers registered')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Register tracker' })).not.toBeInTheDocument();
  });
});

const assignment: TrackerAssignmentDto = {
  id: 'ffffffff-ffff-4fff-8fff-ffffffffffff',
  tracker_id: TRACKER_ID,
  machine_id: MACHINE_ID,
  is_primary: true,
  effective_from: '2026-10-21T10:00:00Z',
  effective_to: null,
  reason: null,
};

async function assignFlow(swap: boolean) {
  const user = userEvent.setup();
  mocks.listMachines.mockResolvedValue(page([MACHINE]));
  mocks.assign.mockResolvedValue(assignment);
  const onAssigned = vi.fn();
  renderWithProviders(
    <AssignTrackerDialog
      tracker={makeTracker()}
      timeZone="UTC"
      onClose={vi.fn()}
      onAssigned={onAssigned}
    />,
    { tenantPermissions: WRITE },
  );
  await user.click(screen.getByRole('combobox', { name: /^Machine/ }));
  await user.click(await screen.findByRole('option', { name: 'EX-01 · Excavator' }));
  await user.click(screen.getByRole('button', { name: 'Next' }));
  const swapBox = await screen.findByRole('checkbox', { name: 'Replace existing primary (swap)' });
  expect(screen.queryByText(SWAP_WARNING)).not.toBeInTheDocument();
  if (swap) {
    await user.click(swapBox);
    expect(screen.getByText(SWAP_WARNING)).toBeInTheDocument();
  }
  await user.click(screen.getByRole('button', { name: 'Next' }));

  expect(await screen.findByText(swap ? 'Yes — swap' : 'No')).toBeInTheDocument();
  if (swap) expect(screen.getByText(SWAP_WARNING)).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Assign tracker' }));
  await waitFor(() => {
    expect(mocks.assign).toHaveBeenCalledTimes(1);
  });
  return { onAssigned };
}

describe('AssignTrackerDialog (assign / swap)', () => {
  it('sends replace_existing_primary: true when swap is chosen, with the warning shown', async () => {
    const { onAssigned } = await assignFlow(true);
    const [tid, body, key] = mocks.assign.mock.calls[0] ?? [];
    expect(tid).toBe(TRACKER_ID);
    expect(body).toMatchObject({
      machine_id: MACHINE_ID,
      is_primary: true,
      replace_existing_primary: true,
      reason: null,
    });
    expect(typeof key).toBe('string');
    expect(onAssigned).toHaveBeenCalledWith(assignment);
  });

  it('sends replace_existing_primary: false by default', async () => {
    await assignFlow(false);
    expect(mocks.assign.mock.calls[0]?.[1]).toMatchObject({ replace_existing_primary: false });
  });
});

describe('IngestionEventsPanel', () => {
  it('explains quarantine reasons', async () => {
    mocks.listIngestionEvents.mockResolvedValue(
      page([
        {
          id: '12121212-1212-4212-8212-121212121212',
          received_at: '2026-10-21T09:00:00Z',
          external_device_id: '999',
          tracker_id: null,
          machine_id: null,
          event_time: '2026-10-21T08:59:00Z',
          status: 'QUARANTINED' as const,
          quarantine_reason: 'UNKNOWN_DEVICE' as const,
          detail: null,
        },
      ]),
    );
    renderWithProviders(
      <IngestionEventsPanel
        timeZone="UTC"
        status=""
        onStatusChange={vi.fn()}
        tracker={null}
        onTrackerChange={vi.fn()}
      />,
      { tenantPermissions: READ },
    );
    expect(await screen.findByText('Unknown device')).toBeInTheDocument();
    // Visible in the row (and in the collapsible legend).
    expect(
      screen.getAllByText('The device identity is not registered to any tracker.').length,
    ).toBeGreaterThan(0);
    expect(screen.getByText('Quarantined')).toBeInTheDocument();
  });
});
