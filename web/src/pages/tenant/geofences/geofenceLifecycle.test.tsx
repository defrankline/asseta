import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { geofenceService } from '../../../api/services/geofenceService';
import type { GeofenceDto, JobSiteDto } from '../../../api/types';
import { STALE_RECORD_MESSAGE } from '../../../components/lifecycle/LifecycleActionDialog';
import { ACTIVE_RECORD } from '../../../test/lifecycleFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { GeofencesPage } from './GeofencesPage';

vi.mock('maplibre-gl', () => import('../../../test/maplibreMock'));
const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof geofenceService.list>(),
  listJobSites: vi.fn<typeof geofenceService.listJobSites>(),
  deactivate: vi.fn<typeof geofenceService.deactivate>(),
  reactivate: vi.fn<typeof geofenceService.reactivate>(),
  deactivateJobSite: vi.fn<typeof geofenceService.deactivateJobSite>(),
  reactivateJobSite: vi.fn<typeof geofenceService.reactivateJobSite>(),
  updateJobSite: vi.fn<typeof geofenceService.updateJobSite>(),
}));
vi.mock('../../../api/services/geofenceService', () => ({ geofenceService: mocks }));
vi.mock('../../../api/services/machineService', () => ({
  machineService: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 }),
  },
}));

const READ = ['tenant.geofence.read'];
const WRITE = ['tenant.geofence.read', 'tenant.geofence.write'];

const SITE: JobSiteDto = {
  id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
  code: 'S1',
  name: 'Quarry',
  address: 'Kunduchi',
  center: { type: 'Point', coordinates: [39.2, -6.8] },
  ...ACTIVE_RECORD,
  version: 4,
};
function fence(overrides: Partial<GeofenceDto> = {}): GeofenceDto {
  return {
    id: 'f1f1f1f1-f1f1-4f1f-8f1f-f1f1f1f1f1f1',
    name: 'Yard',
    kind: 'ALLOWED_AREA',
    shape: 'POLYGON',
    job_site_id: SITE.id,
    corridor_width_m: null,
    source_geometry: {},
    area_geojson: {},
    area_m2: 12345,
    machine_ids: [],
    ...ACTIVE_RECORD,
    version: 2,
    ...overrides,
  };
}

beforeEach(() => {
  mocks.list.mockResolvedValue([fence()]);
  mocks.listJobSites.mockResolvedValue([SITE]);
});

const apiError = (code: string, message: string) =>
  new ApiError({ status: 409, code, message, correlationId: 'g1' });

describe('geofence row actions', () => {
  it('offers only viewing without tenant.geofence.write', async () => {
    const user = userEvent.setup();
    renderWithProviders(<GeofencesPage />, { tenantPermissions: READ });
    await user.click(await screen.findByRole('button', { name: 'Actions for geofence Yard' }));
    expect(screen.getByRole('menuitem', { name: 'View details' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Show on map' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Deactivate' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New geofence' })).not.toBeInTheDocument();
  });

  it('shows every field and the job site in the details drawer', async () => {
    const user = userEvent.setup();
    renderWithProviders(<GeofencesPage />, { tenantPermissions: WRITE });
    await user.click(await screen.findByRole('button', { name: 'Actions for geofence Yard' }));
    await user.click(screen.getByRole('menuitem', { name: 'View details' }));
    const drawer = await screen.findByRole('presentation');
    expect(within(drawer).getByText('Geofence Yard')).toBeInTheDocument();
    expect(within(drawer).getByText('S1 · Quarry')).toBeInTheDocument();
    expect(within(drawer).getByText('All machines')).toBeInTheDocument();
    expect(within(drawer).getByRole('button', { name: 'Deactivate' })).toBeInTheDocument();
  });

  it('deactivates with a reason and the version that was read', async () => {
    const user = userEvent.setup();
    mocks.deactivate.mockResolvedValue(fence({ is_active: false }));
    renderWithProviders(<GeofencesPage />, { tenantPermissions: WRITE });
    await user.click(await screen.findByRole('button', { name: 'Actions for geofence Yard' }));
    await user.click(screen.getByRole('menuitem', { name: 'Deactivate' }));
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(await screen.findByText('A reason is required')).toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Season over');
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    await waitFor(() => {
      expect(mocks.deactivate).toHaveBeenCalledTimes(1);
    });
    const [id, body] = mocks.deactivate.mock.calls[0] ?? [];
    expect(id).toBe(fence().id);
    expect(body).toEqual({ reason: 'Season over', version: 2 });
    await waitFor(() => {
      expect(mocks.list).toHaveBeenCalledTimes(2);
    });
  });

  it('passes the show-inactive flag and reactivates muted geofences', async () => {
    const user = userEvent.setup();
    mocks.reactivate.mockResolvedValue(fence());
    renderWithProviders(<GeofencesPage />, { tenantPermissions: WRITE });
    await screen.findByText('Yard');
    expect(mocks.list).toHaveBeenLastCalledWith(expect.any(AbortSignal), false);
    mocks.list.mockResolvedValue([fence({ is_active: false })]);
    await user.click(screen.getByRole('switch', { name: 'Show inactive geofences' }));
    await waitFor(() => {
      expect(mocks.list).toHaveBeenLastCalledWith(expect.any(AbortSignal), true);
    });
    await waitFor(() => {
      expect(screen.getByText('Yard').closest('tr')).toHaveAttribute('data-muted', 'true');
    });
    await user.click(screen.getByRole('button', { name: 'Actions for geofence Yard' }));
    expect(screen.queryByRole('menuitem', { name: 'Edit' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('menuitem', { name: 'Reactivate' }));
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Back on site');
    await user.click(screen.getByRole('button', { name: 'Reactivate' }));
    await waitFor(() => {
      expect(mocks.reactivate.mock.calls[0]?.[1]).toEqual({ reason: 'Back on site', version: 2 });
    });
  });
});

describe('job site lifecycle', () => {
  it('passes the show-inactive flag for job sites', async () => {
    const user = userEvent.setup();
    renderWithProviders(<GeofencesPage />, { tenantPermissions: READ });
    await screen.findByText('Kunduchi');
    await user.click(screen.getByRole('switch', { name: 'Show inactive job sites' }));
    await waitFor(() => {
      expect(mocks.listJobSites).toHaveBeenLastCalledWith(expect.any(AbortSignal), undefined, true);
    });
  });

  it('shows SITE_IN_USE with its hint in the deactivate dialog', async () => {
    const user = userEvent.setup();
    mocks.deactivateJobSite.mockRejectedValue(apiError('SITE_IN_USE', 'Site is in use.'));
    renderWithProviders(<GeofencesPage />, { tenantPermissions: WRITE });
    await user.click(await screen.findByRole('button', { name: 'Actions for job site S1' }));
    await user.click(screen.getByRole('menuitem', { name: 'Deactivate' }));
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Closed down');
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(
      await screen.findByText(/^SITE_IN_USE: Site is in use\. — The site is still used/),
    ).toBeInTheDocument();
    expect(mocks.deactivateJobSite.mock.calls[0]?.[1]).toEqual({
      reason: 'Closed down',
      version: 4,
    });
  });

  it('lists the site geofences in its drawer', async () => {
    const user = userEvent.setup();
    renderWithProviders(<GeofencesPage />, { tenantPermissions: READ });
    await user.click(await screen.findByRole('button', { name: 'Actions for job site S1' }));
    await user.click(screen.getByRole('menuitem', { name: 'View details' }));
    const drawer = await screen.findByRole('presentation');
    expect(within(drawer).getByRole('table', { name: 'Geofences on this site' })).toHaveTextContent(
      'Yard',
    );
    expect(within(drawer).queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
  });

  async function editToReview(user: ReturnType<typeof userEvent.setup>) {
    await user.click(await screen.findByRole('button', { name: 'Actions for job site S1' }));
    await user.click(screen.getByRole('menuitem', { name: 'Edit' }));
    const name = await screen.findByRole('textbox', { name: /^Name/ });
    expect(name).toHaveValue('Quarry');
    expect(screen.getByRole('textbox', { name: /^Code/ })).toHaveValue('S1');
    await user.clear(name);
    await user.type(name, 'Quarry North');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Save changes' }));
  }

  it('edits a job site prefilled and sends its version and centre', async () => {
    const user = userEvent.setup();
    mocks.updateJobSite.mockResolvedValue({ ...SITE, name: 'Quarry North', version: 5 });
    renderWithProviders(<GeofencesPage />, { tenantPermissions: WRITE });
    await editToReview(user);
    await waitFor(() => {
      expect(mocks.updateJobSite).toHaveBeenCalledTimes(1);
    });
    const [id, body] = mocks.updateJobSite.mock.calls[0] ?? [];
    expect(id).toBe(SITE.id);
    expect(body).toEqual({
      code: 'S1',
      name: 'Quarry North',
      address: 'Kunduchi',
      center: { type: 'Point', coordinates: [39.2, -6.8] },
      version: 4,
    });
  });

  it('offers Reload on STALE_VERSION when editing a job site', async () => {
    const user = userEvent.setup();
    mocks.updateJobSite.mockRejectedValue(apiError('STALE_VERSION', 'Modified'));
    renderWithProviders(<GeofencesPage />, { tenantPermissions: WRITE });
    await editToReview(user);
    expect(await screen.findByText(STALE_RECORD_MESSAGE)).toBeInTheDocument();
    const before = mocks.listJobSites.mock.calls.length;
    await user.click(screen.getByRole('button', { name: 'Reload' }));
    await waitFor(() => {
      expect(mocks.listJobSites.mock.calls.length).toBeGreaterThan(before);
    });
  });
});
