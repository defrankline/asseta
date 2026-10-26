import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CAPABILITY, pathCapability } from '../../../access/capabilities';
import type { AccountabilitySummaryDto } from '../../../api/custodyTypes';
import type { jobService } from '../../../api/services/jobService';
import type { policyService } from '../../../api/services/policyService';
import type { revenueService } from '../../../api/services/revenueService';
import type { ActivityDto, PolicyType } from '../../../api/types';
import { notificationTargetPath } from '../../../notifications/center/display';
import { JOB_ID, MACHINE_ID, makeJob } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import {
  ACTIVITY_ID,
  APPROVAL_ID,
  DIFFERENCE_ID,
  INVOICE_ID,
  makeActivity,
  makeSheetDay,
  makeSheetRow,
  page,
  PURCHASE_ID,
} from '../../../test/revenueFixtures';
import { buildTiles } from '../accountability/accountabilityModel';
import { SegmentChip } from '../engineHours/SegmentDisplay';
import { WorkLogTab } from '../jobDetail/WorkLogTab';
import { PoliciesPage } from '../policies/PoliciesPage';
import { DailySheetDayPage } from './DailySheetDayPage';
import { DailySheetPage } from './DailySheetPage';

const mocks = vi.hoisted(() => ({
  listSheet: vi.fn<typeof revenueService.listSheet>(),
  sheetDay: vi.fn<typeof revenueService.sheetDay>(),
  exportSheetCsv: vi.fn<typeof revenueService.exportSheetCsv>(),
  listActivities: vi.fn<typeof revenueService.listActivities>(),
  listReasons: vi.fn<typeof revenueService.listReasons>(),
  jobActivities: vi.fn<typeof jobService.listActivities>(),
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
vi.mock('../../../api/services/jobService', () => ({
  jobService: { listActivities: mocks.jobActivities },
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
const EXPLAIN = 'tenant.revenue.explain';

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
    expect(within(table).getByRole('link', { name: 'J-100' })).toHaveAttribute(
      'href',
      `/tenant/jobs/${JOB_ID}`,
    );
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
    expect(within(sources).getByRole('link', { name: 'Open invoice' })).toHaveAttribute(
      'href',
      `/tenant/finance/invoices/${INVOICE_ID}`,
    );
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

const ACTIVITY: ActivityDto = {
  id: ACTIVITY_ID,
  job_id: JOB_ID,
  activity_type: 'MOBILIZATION',
  billable: false,
  started_at: '2026-10-20T05:00:00Z',
  ended_at: '2026-10-20T06:30:00Z',
  note: 'Drove to site B',
  client_id: 'c1',
} as ActivityDto;

describe('Job work log', () => {
  beforeEach(() => {
    mocks.jobActivities.mockResolvedValue([ACTIVITY]);
  });

  it('shows the non-revenue status of each entry with Explain', async () => {
    mocks.listActivities.mockResolvedValue(page([makeActivity()]));
    renderWithProviders(
      <WorkLogTab job={makeJob({ status: 'COMPLETED' })} timeZone="UTC" onChanged={vi.fn()} />,
      { tenantPermissions: ['tenant.job.read', READ, EXPLAIN] },
    );
    const table = await screen.findByRole('table', { name: 'Work log' });
    expect(await within(table).findByText('Counts as revenue (not explained)')).toBeInTheDocument();
    expect(within(table).getByRole('button', { name: 'Explain' })).toBeInTheDocument();
    expect(mocks.listActivities).toHaveBeenCalledWith(
      expect.objectContaining({ filters: { job_id: JOB_ID } }),
      expect.any(AbortSignal),
    );
  });

  it('links an entry under approval to its record', async () => {
    mocks.listActivities.mockResolvedValue(
      page([makeActivity({ approval_id: APPROVAL_ID, approval_status: 'PROPOSED' })]),
    );
    renderWithProviders(
      <WorkLogTab job={makeJob({ status: 'COMPLETED' })} timeZone="UTC" onChanged={vi.fn()} />,
      { tenantPermissions: ['tenant.job.read', READ, EXPLAIN] },
    );
    expect(
      await screen.findByRole('link', { name: 'Explanation awaiting decision' }),
    ).toHaveAttribute('href', `/tenant/non-revenue-approvals/${APPROVAL_ID}`);
    expect(screen.queryByRole('button', { name: 'Explain' })).not.toBeInTheDocument();
  });

  it('asks nothing while revenue checks are off', async () => {
    mocks.listActivities.mockClear();
    renderWithProviders(
      <WorkLogTab job={makeJob({ status: 'COMPLETED' })} timeZone="UTC" onChanged={vi.fn()} />,
      {
        tenantPermissions: ['tenant.job.read', READ, EXPLAIN],
        disabledCapabilities: [CAPABILITY.revenue],
      },
    );
    await screen.findByRole('table', { name: 'Work log' });
    expect(screen.queryByText('Non-revenue approval')).not.toBeInTheDocument();
    expect(mocks.listActivities).not.toHaveBeenCalled();
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
            job_id: JOB_ID,
            job_number: 'J-100',
            activity_type: 'MOBILIZATION',
            approved: null,
            proposal: null,
          }}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole('link')).toHaveTextContent(
      'Movement (mobilization) · Job J-100 · 1.5 h',
    );
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
