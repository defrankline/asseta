import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { fleetService } from '../../../api/services/fleetService';
import type { TrackPointDto } from '../../../api/types';
import { lastMap } from '../../../test/maplibreMock';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { HistoryPlayback } from './HistoryPlayback';
import { HistoryTab } from './HistoryTab';
import { validateHistoryRange } from './historyRange';

vi.mock('maplibre-gl', () => import('../../../test/maplibreMock'));

const mocks = vi.hoisted(() => ({ history: vi.fn<typeof fleetService.history>() }));
vi.mock('../../../api/services/fleetService', () => ({
  fleetService: { history: mocks.history },
}));

function point(overrides: Partial<TrackPointDto>): TrackPointDto {
  return {
    event_time: '2026-10-20T08:00:00Z',
    longitude: 39.2,
    latitude: -6.8,
    accuracy_m: 8,
    speed_kmh: 0,
    heading_deg: null,
    ignition: null,
    quality: 'GOOD',
    is_late: false,
    received_at: '2026-10-20T08:00:05Z',
    ...overrides,
  };
}

const POINTS: TrackPointDto[] = [
  point({}),
  point({ event_time: '2026-10-20T08:10:00Z', longitude: 39.25, latitude: -6.81, is_late: true }),
  point({ event_time: '2026-10-20T08:20:00Z', longitude: 39.3, quality: 'LOW_ACCURACY' }),
];

function playbackCoords(): unknown {
  const data = lastMap().getSource('history-playback')?.data as {
    features: { geometry: { coordinates: number[] } }[];
  };
  return data.features[0]?.geometry.coordinates;
}

describe('HistoryPlayback', () => {
  it('moves the playback marker through the points with the slider', async () => {
    renderWithProviders(
      <HistoryPlayback points={POINTS} stops={[]} timeZone="UTC" queryKey="q1" />,
    );
    expect(screen.getByText('Point 1 of 3')).toBeInTheDocument();
    expect(screen.getByText('20 Oct 2026, 08:00:00')).toBeInTheDocument();
    await waitFor(() => {
      expect(playbackCoords()).toEqual([39.2, -6.8]);
    });

    fireEvent.change(screen.getByRole('slider', { name: 'Playback position' }), {
      target: { value: '1' },
    });
    expect(await screen.findByText('Point 2 of 3')).toBeInTheDocument();
    expect(screen.getByText('20 Oct 2026, 08:10:00')).toBeInTheDocument();
    expect(screen.getByText('Late')).toBeInTheDocument();
    await waitFor(() => {
      expect(playbackCoords()).toEqual([39.25, -6.81]);
    });

    fireEvent.change(screen.getByRole('slider', { name: 'Playback position' }), {
      target: { value: '2' },
    });
    expect(await screen.findByText('Point 3 of 3')).toBeInTheDocument();
    expect(screen.getByText('Low quality')).toBeInTheDocument();
    await waitFor(() => {
      expect(playbackCoords()).toEqual([39.3, -6.8]);
    });
  });

  it('flags late and low-quality points for distinct map styling', async () => {
    renderWithProviders(
      <HistoryPlayback points={POINTS} stops={[]} timeZone="UTC" queryKey="q1" />,
    );
    await waitFor(() => {
      expect(lastMap().getSource('history-route')).toBeDefined();
    });
    const data = lastMap().getSource('history-route')?.data as {
      features: { properties: Record<string, unknown> }[];
    };
    const pts = data.features.filter((f) => f.properties.kind === 'point');
    expect(pts.map((f) => [f.properties.late, f.properties.lowQuality])).toEqual([
      [false, false],
      [true, false],
      [false, true],
    ]);
  });
});

describe('HistoryTab range validation', () => {
  it('rejects ranges longer than 31 days without calling the API', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <HistoryTab
        machineId="m1"
        timeZone="UTC"
        initialRange={{ from: '2026-08-01T00:00:00Z', to: '2026-09-15T00:00:00Z' }}
      />,
      { tenantPermissions: ['tenant.fleet.read'] },
    );
    await user.click(screen.getByRole('button', { name: 'Load history' }));
    expect(await screen.findByText('The range can be at most 31 days.')).toBeInTheDocument();
    expect(mocks.history).not.toHaveBeenCalled();
  });

  it('validates order and accepts a 31-day range', () => {
    expect(validateHistoryRange('2026-10-02T00:00:00Z', '2026-10-01T00:00:00Z')).toBe(
      'The end must be after the start.',
    );
    expect(validateHistoryRange('2026-09-01T00:00:00Z', '2026-10-02T00:00:00Z')).toBeNull();
  });

  it('loads history for a valid range', async () => {
    const user = userEvent.setup();
    mocks.history.mockResolvedValue({
      machine_id: 'm1',
      points: POINTS,
      truncated: true,
      stops: [],
      distance_km: 12.345,
      site_visits: [],
      policy_version: 'TRACKING:v3',
    });
    const range = { from: '2026-10-20T00:00:00Z', to: '2026-10-21T00:00:00Z' };
    renderWithProviders(<HistoryTab machineId="m1" timeZone="UTC" initialRange={range} />, {
      tenantPermissions: ['tenant.fleet.read'],
    });
    await user.click(screen.getByRole('button', { name: 'Load history' }));
    expect(await screen.findByText('12.35 km')).toBeInTheDocument();
    expect(screen.getByText(/only part of the track is shown/)).toBeInTheDocument();
    expect(mocks.history).toHaveBeenCalledWith('m1', range.from, range.to, expect.anything());
  });
});
