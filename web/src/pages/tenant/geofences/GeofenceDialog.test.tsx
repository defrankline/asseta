import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { geofenceService } from '../../../api/services/geofenceService';
import type { GeofenceDto, GeofenceIn } from '../../../api/types';
import { lastMap } from '../../../test/maplibreMock';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { GeofenceDialog } from './GeofenceDialog';

vi.mock('maplibre-gl', () => import('../../../test/maplibreMock'));
const mocks = vi.hoisted(() => ({
  create: vi.fn<typeof geofenceService.create>(),
  update: vi.fn<typeof geofenceService.update>(),
}));
vi.mock('../../../api/services/geofenceService', () => ({
  geofenceService: { create: mocks.create, update: mocks.update },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: { list: vi.fn() },
}));

function saved(body: GeofenceIn): GeofenceDto {
  return {
    id: 'f1f1f1f1-f1f1-4f1f-8f1f-f1f1f1f1f1f1',
    name: body.name,
    kind: body.kind,
    shape: body.polygon ? 'POLYGON' : 'CORRIDOR',
    job_site_id: null,
    corridor_width_m: body.corridor_width_m ?? null,
    source_geometry: {},
    area_geojson: {},
    area_m2: 12345,
    machine_ids: [],
    is_active: true,
    version: 1,
  };
}

async function start(user: ReturnType<typeof userEvent.setup>) {
  const onSaved = vi.fn();
  renderWithProviders(
    <GeofenceDialog sites={[]} machineLabels={new Map()} onClose={vi.fn()} onSaved={onSaved} />,
    { tenantPermissions: ['tenant.geofence.read', 'tenant.geofence.write'] },
  );
  await user.type(screen.getByLabelText(/^Name/), 'Yard');
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await waitFor(() => {
    expect(lastMap().getSource('draw-preview')).toBeDefined();
  });
  return onSaved;
}

function clickMap(lon: number, lat: number) {
  act(() => {
    lastMap().click(lon, lat);
  });
}

describe('GeofenceDialog drawing', () => {
  it('produces a closed GeoJSON polygon ring', async () => {
    const user = userEvent.setup();
    mocks.create.mockImplementation((body) => Promise.resolve(saved(body)));
    const onSaved = await start(user);
    clickMap(39.0, -6.0);
    clickMap(39.1, -6.0);
    expect(screen.getByRole('button', { name: 'Close ring' })).toBeDisabled();
    clickMap(39.1, -6.1);
    expect(screen.getByText('3 vertices · ring open')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Close the ring to finish the polygon')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Close ring' }));
    expect(screen.getByText('3 vertices · ring closed')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Create geofence' }));

    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledTimes(1);
    });
    const body = mocks.create.mock.calls[0]?.[0];
    expect(body?.polygon).toEqual({
      type: 'Polygon',
      coordinates: [
        [
          [39.0, -6.0],
          [39.1, -6.0],
          [39.1, -6.1],
          [39.0, -6.0],
        ],
      ],
    });
    const ring = body?.polygon?.coordinates[0] ?? [];
    expect(ring[0]).toEqual(ring[ring.length - 1]);
    expect(body?.corridor).toBeNull();
    expect(body?.corridor_width_m).toBeNull();
    expect(body?.machine_ids).toEqual([]);
    expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ area_m2: 12345 }));
  });

  it('undo removes the last vertex', async () => {
    const user = userEvent.setup();
    await start(user);
    clickMap(39.0, -6.0);
    clickMap(39.1, -6.0);
    await user.click(screen.getByRole('button', { name: 'Undo' }));
    expect(screen.getByText('1 vertices · ring open')).toBeInTheDocument();
  });

  it('sends a corridor polyline with its width', async () => {
    const user = userEvent.setup();
    mocks.create.mockImplementation((body) => Promise.resolve(saved(body)));
    await start(user);
    await user.click(screen.getByRole('radio', { name: /Corridor/ }));
    clickMap(39.0, -6.0);
    clickMap(39.2, -6.05);
    await user.type(screen.getByLabelText(/^Corridor width/), '25');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Create geofence' }));
    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledTimes(1);
    });
    const body = mocks.create.mock.calls[0]?.[0];
    expect(body?.corridor).toEqual({
      type: 'LineString',
      coordinates: [
        [39.0, -6.0],
        [39.2, -6.05],
      ],
    });
    expect(body?.corridor_width_m).toBe(25);
    expect(body?.polygon).toBeNull();
  });
});
