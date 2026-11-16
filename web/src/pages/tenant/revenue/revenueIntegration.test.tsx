import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CAPABILITY, pathCapability } from '../../../access/capabilities';
import type { AccountabilitySummaryDto } from '../../../api/custodyTypes';
import type { policyService } from '../../../api/services/policyService';
import type { revenueService } from '../../../api/services/revenueService';
import type { PolicyType } from '../../../api/types';
import { notificationTargetPath } from '../../../notifications/center/display';
import { MACHINE_ID } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import {
  APPROVAL_ID,
  DIFFERENCE_ID,
  makeSheetDay,
  makeSheetRow,
  page,
  PURCHASE_ID,
} from '../../../test/revenueFixtures';
import { buildTiles } from '../accountability/accountabilityModel';
import { SegmentChip } from '../engineHours/SegmentDisplay';
import { PoliciesPage } from '../policies/PoliciesPage';
import { DailySheetDayPage } from './DailySheetDayPage';
import { DailySheetPage } from './DailySheetPage';

const mocks = vi.hoisted(() => ({
  listSheet: vi.fn<typeof revenueService.listSheet>(),
  sheetDay: vi.fn<typeof revenueService.sheetDay>(),
  exportSheetCsv: vi.fn<typeof revenueService.exportSheetCsv>(),
  listActivities: vi.fn<typeof revenueService.listActivities>(),
  listReasons: vi.fn<typeof revenueService.listReasons>(),
  effective: vi.fn<typeof policyService.effective>(),
  versions: vi.fn<typeof policyService.versions>(),
  saveBlob: vi.fn(),
}));
vi.mock('../../../api/services/revenueService', () => ({
  revenueService: {
    listSheet: mocks.listSheet,
    sheetDay: mocks.sheetDay,
    exportSheetCsv: mocks.exportSheetCsv,
    listActivities: mocks.listActivities,
    listReasons: mocks.listReasons,
  },
}));
vi.mock('../../../api/services/policyService', () => ({
  policyService: { effective: mocks.effective, versions: mocks.versions },
}));
vi.mock('../../../api/services/geofenceService', () => ({
  geofenceService: { listJobSites: vi.fn().mockResolvedValue([]) },
}));
vi.mock('../../../api/services/machineService', () => ({ machineService: { list: vi.fn() } }));
vi.mock('../../../components/data/exportFile', () => ({ saveBlob: mocks.saveBlob }));

const READ = 'tenant.revenue.read';

beforeEach(() => {
  mocks.listSheet.mockResolvedValue(page([makeSheetRow()]));
  mocks.sheetDay.mockResolvedValue(makeSheetDay());
});

describe('Daily machine sheet', () => {
  it('shows hour buckets, money per currency and flags linking onwards', async () => {
    renderWithProviders(<DailySheetPage />, { tenantPermissions: [READ] });
    const table = await screen.findByRole('table');
    expect(within(table).getByText('EX-01 · Excavator')).toBeInTheDocument();
    expect(within(table).getByText(/Movement \(mobilization\) 1\.00 h/)).toBeInTheDocument();
    expect(within(table).getByText(/0\.50 h awaiting approval/)).toBeInTheDocument();
    expect(within(table).getByText(/500,000/)).toBeInTheDocument();
    expect(within(table).getAllByText(/100\.00/)[0]).toBeInTheDocument();
    expect(within(table).getByRole('link', { name: 'Revenue difference' })).toHaveAttribute(
      'href',
      `/tenant/engine-hours/daily-sheet/${MACHINE_ID}/2026-10-20`,
    );
    expect(within(table).getByRole('link', { name: 'Hours to explain' })).toHaveAttribute(
      'href',
      `/tenant/engine-hours/machines/${MACHINE_ID}`,
    );
    expect(within(table).queryByRole('link', { name: 'J-100' })).toBeNull();
  });

  it('exports the CSV with the current filters', async () => {
    const user = userEvent.setup();
    const blob = new Blob(['a,b']);
    mocks.exportSheetCsv.mockResolvedValue({ blob, filename: 'sheet.csv' });
    renderWithProviders(<DailySheetPage />, { tenantPermissions: [READ] });
    await screen.findByRole('table');
    await user.type(screen.getByLabelText('From day'), '2026-10-01');
    await user.type(screen.getByLabelText('To day'), '2026-10-07');
    await user.click(screen.getByRole('button', { name: 'Export CSV' }));
    await waitFor(() => {
      expect(mocks.exportSheetCsv).toHaveBeenCalledWith({
        day_from: '2026-10-01',
        day_to: '2026-10-07',
      });
    });
    expect(mocks.saveBlob).toHaveBeenCalledWith(blob, 'sheet.csv');
  });

  it('refuses a range longer than 93 days', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DailySheetPage />, { tenantPermissions: [READ] });
    await screen.findByRole('table');
    await user.type(screen.getByLabelText('From day'), '2026-01-01');
    await user.type(screen.getByLabelText('To day'), '2026-06-01');
    expect(screen.getByText('Choose at most 93 days at a time.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Export CSV' })).toBeDisabled();
  });

  it('drills into one machine-day: flags, money sources, readings and fuel', async () => {
    renderWithProviders(
      <Routes>
        <Route
          path="/tenant/engine-hours/daily-sheet/:machineId/:day"
          element={<DailySheetDayPage />}
        />
      </Routes>,
      {
        tenantPermissions: [READ],
        route: `/tenant/engine-hours/daily-sheet/${MACHINE_ID}/2026-10-20`,
      },
    );
    expect(await screen.findByRole('link', { name: 'Revenue difference' })).toHaveAttribute(
      'href',
      `/tenant/revenue-differences/${DIFFERENCE_ID}`,
    );
    expect(mocks.sheetDay).toHaveBeenCalledWith(MACHINE_ID, '2026-10-20', expect.any(AbortSignal));
    const sources = screen.getByRole('table', { name: 'Money sources' });
    expect(within(sources).queryByRole('link', { name: 'Open invoice' })).toBeNull();
    expect(within(sources).getByRole('link', { name: 'Open purchase' })).toHaveAttribute(
      'href',
      `/tenant/hours/purchases/${PURCHASE_ID}`,
    );
    expect(screen.getByRole('table', { name: 'Readings' })).toHaveTextContent('1000.0');
    expect(screen.getByRole('table', { name: 'Fuel' })).toHaveTextContent('120.0');
    expect(screen.getByRole('table', { name: 'Engine-hour segments' })).toHaveTextContent(
      'Customer work',
    );
  });
});

describe('Daily machine sheet: engine running without work and fuel per engine hour (DEC-031 S1/S2)', () => {
  it('shows litres per engine hour in the list', async () => {
    renderWithProviders(<DailySheetPage />, { tenantPermissions: [READ] });
    expect(await screen.findByText('12.00 L per engine h')).toBeInTheDocument();
  });

  it('links the machine-day case and shows the fuel rate on the day', async () => {
    mocks.sheetDay.mockResolvedValue(
      makeSheetDay({
        flags: ['ENGINE_ON_WITHOUT_JOB'],
        flag_records: [
          { flag: 'ENGINE_ON_WITHOUT_JOB', record_type: 'anomaly_case', record_id: 'case-1' },
        ],
      }),
    );
    renderWithProviders(
      <Routes>
        <Route
          path="/tenant/engine-hours/daily-sheet/:machineId/:day"
          element={<DailySheetDayPage />}
        />
      </Routes>,
      {
        tenantPermissions: [READ],
        route: `/tenant/engine-hours/daily-sheet/${MACHINE_ID}/2026-10-20`,
      },
    );
    expect(
      await screen.findByRole('link', { name: 'Engine on without reported work' }),
    ).toHaveAttribute('href', '/tenant/cases/case-1');
    expect(screen.getByText('12.00 L per engine h')).toBeInTheDocument();
  });

  it('shows no rate without engine hours', async () => {
    mocks.sheetDay.mockResolvedValue(makeSheetDay({ fuel_litres_per_engine_hour: null }));
    renderWithProviders(
      <Routes>
        <Route
          path="/tenant/engine-hours/daily-sheet/:machineId/:day"
          element={<DailySheetDayPage />}
        />
      </Routes>,
      {
        tenantPermissions: [READ],
        route: `/tenant/engine-hours/daily-sheet/${MACHINE_ID}/2026-10-20`,
      },
    );
    expect(await screen.findByText('— (no engine hours)')).toBeInTheDocument();
  });
});

const SUMMARY = {
  as_of: '2026-10-21T12:00:00Z',
  policy_version: 'v1',
  hidden_tiles: [],
  unavailable_tiles: [],
  disabled_capabilities: [],
  revenue_differences: {
    open: 2,
    awaiting_decision: 1,
    amounts: [{ currency: 'TZS', count: 3, amount: '250000' }],
    oldest_open_days: 4,
    window_days: 30,
    explained_in_window: 1,
    confirmed_in_window: 0,
    cleared_in_window: 2,
    items: [
      {
        id: DIFFERENCE_ID,
        machine_id: MACHINE_ID,
        machine_code: 'EX-01',
        period_key: '2026-10-20',
        local_from: '2026-10-20',
        local_to: '2026-10-20',
        currency: 'TZS',
        difference: '200000',
        status: 'OPEN',
      },
    ],
  },
} as unknown as AccountabilitySummaryDto;

describe('Revenue checks across the console', () => {
  it('builds the revenue differences tile, linking to the list and records', () => {
    const tile = buildTiles(SUMMARY, () => true).find((t) => t.key === 'revenue_differences');
    expect(tile?.value).toBe(3);
    expect(tile?.to).toBe('/tenant/revenue-differences?status=OPEN');
    expect(tile?.description).toBe('Oldest open 4 days');
    const rows = tile?.rows ?? [];
    expect(rows.find((r) => r.key === 'awaiting')?.to).toBe(
      '/tenant/revenue-differences?status=EXPLANATION_PROPOSED',
    );
    expect(rows.find((r) => r.key === DIFFERENCE_ID)?.to).toBe(
      `/tenant/revenue-differences/${DIFFERENCE_ID}`,
    );
  });

  it('drops the tile when revenue checks are off', () => {
    const off = { ...SUMMARY, disabled_capabilities: [CAPABILITY.revenue] };
    expect(buildTiles(off, () => true).some((t) => t.key === 'revenue_differences')).toBe(false);
  });

  it('opens revenue notifications at their records (no link when switched off)', () => {
    expect(
      notificationTargetPath(null, { kind: 'REVENUE_DIFFERENCE', record_id: DIFFERENCE_ID }),
    ).toBe(`/tenant/revenue-differences/${DIFFERENCE_ID}`);
    expect(
      notificationTargetPath(null, { kind: 'NON_REVENUE_APPROVAL', record_id: APPROVAL_ID }),
    ).toBe(`/tenant/non-revenue-approvals/${APPROVAL_ID}`);
    expect(
      notificationTargetPath(
        { entity: 'revenue_difference', id: DIFFERENCE_ID, path: null },
        undefined,
        new Set([CAPABILITY.revenue]),
      ),
    ).toBeNull();
    expect(pathCapability('/tenant/engine-hours/daily-sheet')).toBe(CAPABILITY.revenue);
    expect(pathCapability('/tenant/engine-hours/machines/x')).toBe(CAPABILITY.engineHours);
  });

  it('shows non-revenue time in the engine-hour ledger as its own segment', () => {
    render(
      <MemoryRouter>
        <SegmentChip
          segment={{
            kind: 'NON_REVENUE',
            hours: '1.5',
            classification: 'NOT_APPLICABLE',
            job_id: null,
            job_number: null,
            activity_type: 'MOBILIZATION',
            approved: null,
            proposal: null,
          }}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.getByText('Movement (mobilization) · 1.5 h')).toBeInTheDocument();
  });

  it('renders the revenue checks policy labels', async () => {
    const user = userEvent.setup();
    mocks.effective.mockImplementation((ptype: PolicyType) =>
      Promise.resolve({
        policy_type: ptype,
        version_stamp: `${ptype}:P1`,
        values:
          ptype === 'REVENUE_RECONCILIATION'
            ? {
                enabled: true,
                non_revenue_activity_types: ['MOBILIZATION'],
                non_revenue_requires_approval: true,
                unexplained_hours_treatment: 'EXPECT_REVENUE',
                period: 'WEEK',
              }
            : { billable_hours_increment: '0.1', rounding: 'HALF_UP' },
      }),
    );
    mocks.versions.mockResolvedValue([]);
    renderWithProviders(<PoliciesPage />, {
      tenantPermissions: ['tenant.policy.read', 'tenant.geofence.read'],
    });
    await user.click(screen.getByRole('combobox', { name: 'Policy type' }));
    await user.click(await screen.findByRole('option', { name: 'Revenue checks' }));
    const table = await screen.findByRole('table', { name: 'Effective policy values' });
    await waitFor(() => {
      expect(within(table).getByText('Revenue checks switched on')).toBeInTheDocument();
    });
    expect(within(table).getByText('Work-log types that are not revenue')).toBeInTheDocument();
    expect(within(table).getByText('Movement (mobilization)')).toBeInTheDocument();
    expect(within(table).getByText('Non-revenue time needs approval')).toBeInTheDocument();
    expect(within(table).getByText('Expected as revenue until approved')).toBeInTheDocument();
  });
});
