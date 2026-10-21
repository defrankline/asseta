import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { jobService } from '../../../api/services/jobService';
import type { machineService } from '../../../api/services/machineService';
import type { meterService } from '../../../api/services/meterService';
import { NOT_COMPARED_TEXT } from '../../../components/meter/TrackerComparison';
import { MACHINE, makeCapture, makeException, makeSummary } from '../../../test/jobFixtures';
import { instances } from '../../../test/maplibreMock';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { JobDetailPage } from './JobDetailPage';

vi.mock('maplibre-gl', () => import('../../../test/maplibreMock'));

const mocks = vi.hoisted(() => ({
  summary: vi.fn<typeof jobService.summary>(),
  listActivities: vi.fn<typeof jobService.listActivities>(),
  get: vi.fn<typeof machineService.get>(),
  listCaptures: vi.fn<typeof meterService.listCaptures>(),
  listExceptions: vi.fn<typeof meterService.listExceptions>(),
  attachmentUrl: vi.fn<typeof meterService.attachmentUrl>(),
}));
vi.mock('../../../api/services/jobService', () => ({
  jobService: { summary: mocks.summary, listActivities: mocks.listActivities },
}));
vi.mock('../../../api/services/machineService', () => ({ machineService: { get: mocks.get } }));
vi.mock('../../../api/services/meterService', () => ({
  meterService: {
    listCaptures: mocks.listCaptures,
    listExceptions: mocks.listExceptions,
    attachmentUrl: mocks.attachmentUrl,
  },
}));

const PERMS = ['tenant.job.read', 'tenant.machine.read', 'tenant.meter.read'];

beforeEach(() => {
  mocks.summary.mockResolvedValue(makeSummary());
  mocks.get.mockResolvedValue(MACHINE);
  mocks.listActivities.mockResolvedValue([]);
  mocks.listCaptures.mockResolvedValue([
    makeCapture({ state: 'PROVISIONAL' }),
    makeCapture({
      id: 'ffffffff-0000-4000-8000-000000000002',
      kind: 'CLOSING',
      capture_mode: 'MANUAL',
      reading: '1208.8',
      ocr_value: null,
      ocr_confidence: null,
      gps_status: 'PERMISSION_DENIED',
      latitude: null,
      longitude: null,
      accuracy_m: null,
      location_captured_at: null,
      photo_attachment_id: null,
      photo_sha256: null,
      tracker_comparison: {
        compared: false,
        reason: 'no tracker position within comparison window',
      },
    }),
  ]);
  mocks.listExceptions.mockResolvedValue({
    items: [makeException()],
    total: 1,
    page: 1,
    page_size: 200,
  });
});

describe('JobDetailPage', () => {
  it('shows meter hours and billable hours separately with the explanation', async () => {
    renderWithProviders(<JobDetailPage />, { tenantPermissions: PERMS });
    const meter = await screen.findByRole('group', { name: 'Meter hours' });
    const billable = screen.getByRole('group', { name: 'Billable hours' });
    const nonBillable = screen.getByRole('group', { name: 'Non-billable hours' });
    expect(within(meter).getByText('8.4 h')).toBeInTheDocument();
    expect(within(billable).getByText('8.0 h')).toBeInTheDocument();
    expect(within(nonBillable).getByText('1.50 h')).toBeInTheDocument();
    expect(screen.getByText(/Engine\/meter hours are not billable hours/)).toBeInTheDocument();
    expect(screen.getByText('EX-01 · Excavator')).toBeInTheDocument();
    expect(screen.getByText('Not billing ready')).toBeInTheDocument();
  });

  it('renders capture evidence with tracker comparison, not-compared state and findings', async () => {
    renderWithProviders(<JobDetailPage />, { tenantPermissions: PERMS });
    const opening = await screen.findByLabelText('Opening reading 1200.4');
    expect(within(opening).getByText('Provisional — requires review')).toBeInTheDocument();
    expect(within(opening).getByText('412.3 m')).toBeInTheDocument();
    expect(within(opening).getByText('162 m')).toBeInTheDocument();
    expect(
      within(opening).getByText('Outside allowed distance — requires review'),
    ).toBeInTheDocument();
    expect(within(opening).getByRole('region', { name: 'Reading location' })).toBeInTheDocument();
    expect(
      within(opening).getByText(
        'Phone fix 412.3 m from the machine tracker position at the same time (offset 10 s); allowed 162 m.',
      ),
    ).toBeInTheDocument();

    const closing = screen.getByLabelText('Closing reading 1208.8');
    expect(within(closing).getByText(new RegExp(NOT_COMPARED_TEXT))).toBeInTheDocument();
    expect(within(closing).getByText('Permission denied')).toBeInTheDocument();
    expect(within(closing).getByText(/None recorded/)).toBeInTheDocument();
    expect(
      within(closing).getByText(/No map: this reading has no GPS coordinates/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/fraud/i)).not.toBeInTheDocument();
  });

  it('opens the capture photo on demand and keeps the hash as secondary info', async () => {
    const user = userEvent.setup();
    mocks.attachmentUrl.mockResolvedValue({
      url: 'https://files.test/p.jpg',
      expires_in_seconds: 120,
    });
    renderWithProviders(<JobDetailPage />, { tenantPermissions: PERMS });
    const opening = await screen.findByLabelText('Opening reading 1200.4');
    expect(within(opening).getByText(/SHA-256 abababababab…/)).toBeInTheDocument();
    expect(mocks.attachmentUrl).not.toHaveBeenCalled();
    await user.click(within(opening).getByRole('button', { name: 'View photo' }));
    expect(await within(opening).findByRole('img', { name: 'Evidence thumbnail' })).toHaveAttribute(
      'src',
      'https://files.test/p.jpg',
    );
    expect(mocks.attachmentUrl).toHaveBeenCalledWith(makeCapture().photo_attachment_id);
    const closing = screen.getByLabelText('Closing reading 1208.8');
    expect(within(closing).getByText('No photo')).toBeInTheDocument();
  });

  it('draws the tracker point beside the phone fix on the capture map', async () => {
    renderWithProviders(<JobDetailPage />, { tenantPermissions: PERMS });
    const opening = await screen.findByLabelText('Opening reading 1200.4');
    expect(within(opening).getByText(/Green: machine tracker position/)).toBeInTheDocument();
    const capture = makeCapture();
    await waitFor(() => {
      expect(instances.some((m) => `capture-${capture.id}` in m.sources)).toBe(true);
    });
    const map = instances.find((m) => `capture-${capture.id}` in m.sources);
    const data = map?.sources[`capture-${capture.id}`]?.data as {
      features: {
        properties: { role: string };
        geometry: { type: string; coordinates: unknown };
      }[];
    };
    const byRole = new Map(data.features.map((f) => [f.properties.role, f.geometry]));
    expect(byRole.get('phone')).toEqual({ type: 'Point', coordinates: [39.28, -6.8] });
    expect(byRole.get('tracker')).toEqual({ type: 'Point', coordinates: [39.2812, -6.8037] });
    expect([...byRole.keys()].sort()).toEqual(
      ['allowed', 'link', 'phone', 'phone-accuracy', 'tracker', 'tracker-accuracy'].sort(),
    );
  });

  it('hides the readings tab without meter read permission', async () => {
    renderWithProviders(<JobDetailPage />, { tenantPermissions: ['tenant.job.read'] });
    expect(await screen.findByRole('tab', { name: 'Work log' })).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Readings & evidence' })).not.toBeInTheDocument();
    expect(mocks.listCaptures).not.toHaveBeenCalled();
  });
});
