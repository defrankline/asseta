import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { fleetService } from '../../../api/services/fleetService';
import type { MachineMapDto } from '../../../api/types';
import { lastMap } from '../../../test/maplibreMock';
import { fakeSocketServer } from '../../../test/fakeWebSocket';
import { acceptSocket, LiveProviders, push } from '../../../test/realtimeHarness';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { FleetMapPage } from './FleetMapPage';

vi.mock('maplibre-gl', () => import('../../../test/maplibreMock'));

const mocks = vi.hoisted(() => ({ map: vi.fn<typeof fleetService.map>() }));
vi.mock('../../../api/services/fleetService', () => ({ fleetService: { map: mocks.map } }));

const minutesAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString();

function machine(overrides: Partial<MachineMapDto>): MachineMapDto {
  return {
    machine_id: 'aaaaaaaa-0000-4000-8000-000000000001',
    asset_code: 'EX-01',
    name: 'Excavator',
    machine_status: 'ACTIVE',
    longitude: 39.2,
    latitude: -6.8,
    accuracy_m: 6,
    position_time: minutesAgo(1),
    last_message_at: minutesAgo(1),
    last_seen_age_seconds: 60,
    position_source: 'TRACKER:T-1',
    position_quality: 'GOOD',
    connectivity: 'LIVE',
    is_live: true,
    reported_work_status: 'UNKNOWN',
    observed_engine: 'ON',
    observed_motion: 'MOVING',
    location_compliance: 'COMPLIANT',
    tracker_id: 'tttttttt-0000-4000-8000-000000000001',
    tracker_state: 'VERIFIED_REPORTING',
    supervisor: 'Asha',
    operator: 'Juma',
    open_alerts: 0,
    policy_version: 'TRACKING:v1',
    ...overrides,
  };
}

const FLEET: MachineMapDto[] = [
  machine({}),
  machine({
    machine_id: 'aaaaaaaa-0000-4000-8000-000000000002',
    asset_code: 'DZ-02',
    name: 'Dozer',
    connectivity: 'STALE',
    is_live: false,
    position_time: minutesAgo(90),
    last_message_at: minutesAgo(90),
    observed_engine: 'UNKNOWN',
    observed_motion: 'UNKNOWN',
    location_compliance: 'UNKNOWN',
    open_alerts: 2,
  }),
  machine({
    machine_id: 'aaaaaaaa-0000-4000-8000-000000000003',
    asset_code: 'GR-03',
    name: 'Grader',
    connectivity: 'NO_TRACKER',
    is_live: false,
    longitude: null,
    latitude: null,
    position_time: null,
    last_message_at: null,
    tracker_id: null,
    tracker_state: null,
  }),
];

const PERMS = ['tenant.fleet.read'];

describe('FleetMapPage', () => {
  it('reloads positions when the server pushes fleet.position changes', async () => {
    mocks.map.mockResolvedValue(FLEET);
    const server = fakeSocketServer();
    renderWithProviders(
      <LiveProviders server={server}>
        <FleetMapPage />
      </LiveProviders>,
      { tenantPermissions: PERMS },
    );
    await screen.findByRole('list', { name: 'Machines' });
    const before = mocks.map.mock.calls.length;
    await acceptSocket(server);
    push(server, 'entity.changed', { entity: 'fleet.position', id: 'm1', action: 'updated' });
    push(server, 'entity.changed', { entity: 'fleet.position', id: 'm2', action: 'updated' });
    await waitFor(
      () => {
        expect(mocks.map.mock.calls.length).toBe(before + 1);
      },
      { timeout: 3_000 },
    );
  });

  it('lists machines, labels stale data as last known and shows the refresh time', async () => {
    mocks.map.mockResolvedValue(FLEET);
    renderWithProviders(<FleetMapPage />, { tenantPermissions: PERMS });
    const list = await screen.findByRole('list', { name: 'Machines' });
    expect(within(list).getByText('EX-01 · Excavator')).toBeInTheDocument();
    expect(within(list).getByText('Live')).toBeInTheDocument();
    expect(within(list).getByText('Stale · last known')).toBeInTheDocument();
    expect(within(list).queryAllByText('Live')).toHaveLength(1);
    expect(within(list).getByText('No position')).toBeInTheDocument();
    expect(within(list).getByText('1 h 30 min ago')).toBeInTheDocument();
    expect(screen.getByText(/Updated at/)).toBeInTheDocument();
    // Only positioned machines become markers.
    await waitFor(() => {
      const data = lastMap().getSource('fleet-machines')?.data as { features: unknown[] };
      expect(data.features).toHaveLength(2);
    });
  });

  it('filters list and markers by connectivity', async () => {
    const user = userEvent.setup();
    mocks.map.mockResolvedValue(FLEET);
    renderWithProviders(<FleetMapPage />, { tenantPermissions: PERMS });
    const list = await screen.findByRole('list', { name: 'Machines' });
    await user.click(screen.getByRole('combobox', { name: 'Connectivity' }));
    await user.click(await screen.findByRole('option', { name: 'Stale (1)' }));
    expect(within(list).queryByText('EX-01 · Excavator')).not.toBeInTheDocument();
    expect(within(list).getByText('DZ-02 · Dozer')).toBeInTheDocument();
    await waitFor(() => {
      const data = lastMap().getSource('fleet-machines')?.data as {
        features: { properties: { machineId: string; live: boolean; hollow: boolean } }[];
      };
      expect(data.features).toHaveLength(1);
      expect(data.features[0]?.properties).toMatchObject({ live: false, hollow: true });
    });
  });

  it('shows status dimensions and a last-known warning for the selected machine', async () => {
    const user = userEvent.setup();
    mocks.map.mockResolvedValue(FLEET);
    renderWithProviders(<FleetMapPage />, { tenantPermissions: PERMS });
    await user.click(await screen.findByText('DZ-02 · Dozer'));
    const panel = screen.getByRole('region', { name: 'Status of DZ-02' });
    expect(within(panel).getByText('Reported work status')).toBeInTheDocument();
    expect(within(panel).getByText('Location compliance')).toBeInTheDocument();
    expect(within(panel).getAllByText('Unknown')).toHaveLength(4);
    expect(within(panel).getByText(/Last known position — not live/)).toBeInTheDocument();
    expect(within(panel).getByRole('link', { name: '2 open' })).toBeInTheDocument();

    // Clicking a marker selects that machine.
    act(() => {
      lastMap().clickLayer('fleet-machines-marker', { machineId: FLEET[0]?.machine_id });
    });
    expect(await screen.findByRole('region', { name: 'Status of EX-01' })).toBeInTheDocument();
  });

  it('refreshes every 30 seconds', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      mocks.map.mockResolvedValue(FLEET);
      renderWithProviders(<FleetMapPage />, { tenantPermissions: PERMS });
      await screen.findByRole('list', { name: 'Machines' });
      expect(mocks.map).toHaveBeenCalledTimes(1);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30_000);
      });
      await waitFor(() => {
        expect(mocks.map).toHaveBeenCalledTimes(2);
      });
    } finally {
      vi.useRealTimers();
    }
  });
});
