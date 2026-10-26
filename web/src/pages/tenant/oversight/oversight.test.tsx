import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CAPABILITY, pathCapability } from '../../../access/capabilities';
import type {
  IdleMachineDto,
  MySiteCheckinsDto,
  ScorecardDetailDto,
  ScorecardRowDto,
  SiteCheckinDto,
  UnbilledJobDto,
} from '../../../api/oversightTypes';
import {
  idleMachineSchema,
  mySiteCheckinsSchema,
  scorecardDetailSchema,
  siteCheckinSchema,
  unbilledJobSchema,
  type oversightService,
} from '../../../api/services/oversightService';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { FieldCheckinPage } from './FieldCheckinPage';
import { IdleMachinesPage } from './IdleMachinesPage';
import { ScorecardPage } from './ScorecardPage';
import { ScorecardPersonPage } from './ScorecardPersonPage';
import { SiteCheckinDetailPage } from './SiteCheckinsPage';
import { UnbilledWorkPage } from './UnbilledWorkPage';

vi.mock('maplibre-gl', () => import('../../../test/maplibreMock'));

const mocks = vi.hoisted(() => ({
  listScorecard: vi.fn<typeof oversightService.listScorecard>(),
  getScorecard: vi.fn<typeof oversightService.getScorecard>(),
  listUnbilledWork: vi.fn<typeof oversightService.listUnbilledWork>(),
  listIdleMachines: vi.fn<typeof oversightService.listIdleMachines>(),
  listCheckins: vi.fn<typeof oversightService.listCheckins>(),
  getCheckin: vi.fn<typeof oversightService.getCheckin>(),
  mine: vi.fn<typeof oversightService.mine>(),
  record: vi.fn<typeof oversightService.record>(),
}));
vi.mock('../../../api/services/oversightService', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  oversightService: {
    listScorecard: mocks.listScorecard,
    getScorecard: mocks.getScorecard,
    listUnbilledWork: mocks.listUnbilledWork,
    listIdleMachines: mocks.listIdleMachines,
    listCheckins: mocks.listCheckins,
    getCheckin: mocks.getCheckin,
    mine: mocks.mine,
    record: mocks.record,
  },
}));
vi.mock('../finance/invoices/CreateInvoiceDialog', () => ({
  CreateInvoiceDialog: ({ customerId, jobIds }: { customerId: string; jobIds: string[] }) => (
    <div role="dialog" aria-label="New hire invoice">
      {`customer ${customerId} jobs ${jobIds.join(',')}`}
    </div>
  ),
}));

const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 25 });

const ROW: ScorecardRowDto = {
  staff_member_id: 's1',
  staff_member_name: 'Asha Mollel',
  staff_kind: 'SUPERVISOR',
  employee_code: 'E-07',
  is_active: true,
  day_from: '2026-10-01',
  day_to: '2026-10-26',
  machines: 2,
  daily_reports_missing: 1,
  daily_reports_late: 2,
  unexplained_hours: '3.5',
  unexplained_items: 1,
  alerts: 4,
  alerts_open: 1,
  alerts_acknowledged: 3,
  avg_hours_to_acknowledge: '2.0',
  max_hours_to_acknowledge: '5.0',
  cash_held: [
    { currency: 'TZS', amount: '150000', held_since: '2026-10-20T08:00:00Z', held_days: 6 },
  ],
  cash_held_too_long: 1,
  cash_differences: 2,
  cash_difference_totals: [{ currency: 'TZS', count: 2, amount: '40000' }],
  cash_differences_near_threshold: 1,
  revenue_differences: 1,
  revenue_difference_totals: [{ currency: 'TZS', count: 1, amount: '90000' }],
  refused_attempts: 0,
  checkins_missed: 1,
  checkins_made: 3,
  pattern_signals: 1,
  items_total: 12,
};

const DETAIL: ScorecardDetailDto = {
  row: ROW,
  records: [
    {
      item: 'UNEXPLAINED_HOURS',
      record_type: 'engine_interval',
      record_id: null,
      at: '2026-10-22T10:00:00Z',
      day: '2026-10-22',
      machine_id: 'm1',
      machine_code: 'EX-01',
      machine_name: 'Excavator',
      hours: '3.5',
      near_threshold: false,
      detail: {},
    },
    {
      item: 'CASH_DIFFERENCE',
      record_type: 'cash_variance',
      record_id: 'v1',
      at: '2026-10-21T10:00:00Z',
      day: '2026-10-21',
      currency: 'TZS',
      amount: '38000',
      status: 'OPEN',
      near_threshold: true,
      detail: {},
    },
    {
      item: 'PATTERN_SIGNAL',
      record_type: 'risk_signal',
      record_id: 'sig1',
      at: '2026-10-23T10:00:00Z',
      day: null,
      near_threshold: false,
      detail: { case_id: 'case1' },
    },
    {
      item: 'MISSED_CHECKIN',
      record_type: 'site_checkin_slot',
      record_id: null,
      at: '2026-10-24T09:00:00Z',
      day: '2026-10-24',
      job_id: 'j9',
      job_number: 'JOB-0009',
      near_threshold: false,
      detail: {},
    },
  ],
};

const UNBILLED: UnbilledJobDto[] = [
  {
    job_id: 'j1',
    job_number: 'JOB-0001',
    machine_id: 'm1',
    machine_code: 'EX-01',
    machine_name: 'Excavator',
    customer_id: 'c1',
    customer_name: 'Juma Construction',
    job_site_id: null,
    supervisor_staff_id: null,
    completed_at: '2026-10-10T10:00:00Z',
    days_unbilled: 16,
    billable_hours: '40',
    currency: 'TZS',
    total: '2000000',
    draft_invoice_id: null,
  },
  {
    job_id: 'j2',
    job_number: 'JOB-0002',
    machine_id: 'm2',
    customer_id: 'c2',
    customer_name: 'Bahari Ltd',
    job_site_id: null,
    supervisor_staff_id: null,
    completed_at: '2026-10-12T10:00:00Z',
    days_unbilled: 14,
    billable_hours: null,
    currency: 'TZS',
    total: null,
    draft_invoice_id: 'inv9',
  },
];

const IDLE: IdleMachineDto = {
  machine_id: 'm3',
  machine_code: 'GR-02',
  machine_name: 'Grader',
  category_id: null,
  idle_since: '2026-10-01T00:00:00Z',
  idle_days: 25,
  last_job_id: 'j7',
  last_job_number: 'JOB-0007',
  last_job_completed_at: '2026-10-01T00:00:00Z',
  last_engine_activity_at: null,
  planned_job_id: 'j8',
  planned_job_number: 'JOB-0008',
};

const CHECKIN: SiteCheckinDto = {
  id: 'ck1',
  client_id: 'cl1',
  staff_member_id: 's1',
  staff_member_name: 'Asha Mollel',
  recorded_by: 'u1',
  recorded_by_name: 'Asha Mollel',
  captured_at: '2026-10-26T09:05:00Z',
  received_at: '2026-10-26T09:05:02Z',
  gps_status: 'FIX',
  latitude: -6.79,
  longitude: 39.21,
  accuracy_m: 12,
  job_site_id: 'site1',
  job_site_name: 'Kigamboni quarry',
  job_id: 'j1',
  job_number: 'JOB-0001',
  distance_m: 84.4,
  within_distance: true,
  source: 'API',
};

const MINE: MySiteCheckinsDto = {
  required: true,
  times: ['09:00', '15:00'],
  window_minutes: 60,
  max_distance_m: 200,
  timezone: 'UTC',
  day_from: '2026-10-20',
  day_to: '2026-10-26',
  slots: [
    {
      scheduled_at: '2026-10-26T09:00:00Z',
      window_minutes: 60,
      status: 'MADE',
      checkin_id: 'ck1',
      job_id: 'j1',
      job_number: 'JOB-0001',
    },
    { scheduled_at: '2026-10-26T15:00:00Z', window_minutes: 60, status: 'DUE' },
  ],
  checkins: [CHECKIN],
};

const SCORECARD_PERMS = ['tenant.oversight.scorecard.read'];
const OVERSIGHT_PERMS = ['tenant.oversight.read', 'tenant.job.read'];

beforeEach(() => {
  mocks.listScorecard.mockResolvedValue(page([ROW]));
  mocks.getScorecard.mockResolvedValue(DETAIL);
  mocks.listUnbilledWork.mockResolvedValue(page(UNBILLED));
  mocks.listIdleMachines.mockResolvedValue(page([IDLE]));
  mocks.getCheckin.mockResolvedValue(CHECKIN);
  mocks.mine.mockResolvedValue(MINE);
  mocks.record.mockResolvedValue(CHECKIN);
});
afterEach(() => {
  Reflect.deleteProperty(navigator, 'geolocation');
});

describe('oversight contract schemas', () => {
  it('accept the server payloads', () => {
    expect(scorecardDetailSchema.validateSync(DETAIL).records).toHaveLength(4);
    expect(unbilledJobSchema.validateSync(UNBILLED[1]).draft_invoice_id).toBe('inv9');
    expect(idleMachineSchema.validateSync(IDLE).planned_job_id).toBe('j8');
    expect(siteCheckinSchema.validateSync(CHECKIN).within_distance).toBe(true);
    expect(mySiteCheckinsSchema.validateSync(MINE).slots[1]?.status).toBe('DUE');
  });

  it('assigns each page to its capability', () => {
    expect(pathCapability('/tenant/scorecard/s1')).toBe(CAPABILITY.scorecard);
    expect(pathCapability('/tenant/unbilled-work')).toBe(CAPABILITY.unbilledWork);
    expect(pathCapability('/tenant/idle-machines')).toBe(CAPABILITY.idleMachines);
    expect(pathCapability('/tenant/site-checkins/ck1')).toBe(CAPABILITY.siteCheckin);
    expect(pathCapability('/tenant/field/check-in')).toBe(CAPABILITY.siteCheckin);
  });
});

describe('People scorecard', () => {
  it('lists people with the period from the link and opens a person for the same period', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <Routes>
        <Route path="/tenant/scorecard" element={<ScorecardPage />} />
        <Route path="/tenant/scorecard/:staffId" element={<div>person page</div>} />
      </Routes>,
      {
        tenantPermissions: SCORECARD_PERMS,
        route: '/tenant/scorecard?day_from=2026-10-01&day_to=2026-10-26',
      },
    );
    expect(await screen.findByText('Asha Mollel')).toBeInTheDocument();
    expect(mocks.listScorecard.mock.calls[0]?.[0].filters).toMatchObject({
      day_from: '2026-10-01',
      day_to: '2026-10-26',
    });
    expect(screen.getByText('1 just under the case threshold')).toBeInTheDocument();
    await user.click(screen.getByText('Asha Mollel'));
    expect(await screen.findByText('person page')).toBeInTheDocument();
  });

  it('groups a person’s records by item, each linking to its own page', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/tenant/scorecard/:staffId" element={<ScorecardPersonPage />} />
      </Routes>,
      { tenantPermissions: SCORECARD_PERMS, route: '/tenant/scorecard/s1?day_from=2026-10-01' },
    );
    const hours = await screen.findByRole('region', { name: 'Unexplained engine hours (1)' });
    expect(within(hours).getByRole('link', { name: 'Open engine-hour ledger' })).toHaveAttribute(
      'href',
      '/tenant/engine-hours/machines/m1',
    );
    const cash = screen.getByRole('region', { name: 'Cash differences (1)' });
    expect(within(cash).getByRole('link', { name: 'Open difference' })).toHaveAttribute(
      'href',
      '/tenant/finance/cash/variances/v1',
    );
    expect(within(cash).getByText('Just under the case threshold')).toBeInTheDocument();
    const repeats = screen.getByRole('region', { name: 'Repeated items raised for review (1)' });
    expect(within(repeats).getByRole('link', { name: 'Open investigation' })).toHaveAttribute(
      'href',
      '/tenant/cases/case1',
    );
    const missed = screen.getByRole('region', { name: 'Missed site check-ins (1)' });
    expect(within(missed).getByRole('link', { name: 'JOB-0009' })).toHaveAttribute(
      'href',
      '/tenant/jobs/j9',
    );
    expect(mocks.getScorecard).toHaveBeenCalledWith(
      's1',
      { day_from: '2026-10-01', day_to: undefined, item: undefined },
      expect.anything(),
    );
  });

  it('drops links into a capability the company switched off', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/tenant/scorecard/:staffId" element={<ScorecardPersonPage />} />
      </Routes>,
      {
        tenantPermissions: SCORECARD_PERMS,
        route: '/tenant/scorecard/s1',
        disabledCapabilities: ['ENGINE_HOURS'],
      },
    );
    const hours = await screen.findByRole('region', { name: 'Unexplained engine hours (1)' });
    expect(within(hours).queryByRole('link')).toBeNull();
  });
});

describe('Unbilled work', () => {
  it('links to the job and draft invoice and starts an invoice for the job', async () => {
    const user = userEvent.setup();
    renderWithProviders(<UnbilledWorkPage />, {
      tenantPermissions: [...OVERSIGHT_PERMS, 'tenant.finance.invoice'],
    });
    expect(await screen.findByRole('link', { name: 'JOB-0001' })).toHaveAttribute(
      'href',
      '/tenant/jobs/j1',
    );
    expect(screen.getByRole('link', { name: 'Open draft invoice' })).toHaveAttribute(
      'href',
      '/tenant/finance/invoices/inv9',
    );
    await user.click(screen.getByRole('button', { name: 'Create invoice' }));
    expect(screen.getByRole('dialog', { name: 'New hire invoice' })).toHaveTextContent(
      'customer c1 jobs j1',
    );
  });

  it('offers no invoice action without the invoicing permission', async () => {
    renderWithProviders(<UnbilledWorkPage />, { tenantPermissions: OVERSIGHT_PERMS });
    expect(await screen.findByRole('link', { name: 'JOB-0001' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Create invoice' })).toBeNull();
  });
});

describe('Idle machines', () => {
  it('links to the machine, its last job and its planned job', async () => {
    renderWithProviders(<IdleMachinesPage />, { tenantPermissions: OVERSIGHT_PERMS });
    expect(await screen.findByRole('link', { name: 'GR-02 · Grader' })).toHaveAttribute(
      'href',
      '/tenant/machines/m3',
    );
    expect(screen.getByRole('link', { name: 'JOB-0007' })).toHaveAttribute(
      'href',
      '/tenant/jobs/j7',
    );
    expect(screen.getByRole('link', { name: 'JOB-0008' })).toHaveAttribute(
      'href',
      '/tenant/jobs/j8',
    );
  });
});

describe('Site check-ins', () => {
  it('shows one check-in with its distance, map and job', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/tenant/site-checkins/:id" element={<SiteCheckinDetailPage />} />
      </Routes>,
      { tenantPermissions: OVERSIGHT_PERMS, route: '/tenant/site-checkins/ck1' },
    );
    expect(await screen.findByText('84 m from the site (within the distance)')).toBeInTheDocument();
    expect(screen.getAllByText('Within the distance').length).toBeGreaterThan(0);
    expect(screen.getByRole('region', { name: 'Location' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open the job' })).toHaveAttribute(
      'href',
      '/tenant/jobs/j1',
    );
  });

  it('lets a supervisor check in from the browser with a real GPS fix', async () => {
    const user = userEvent.setup();
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: {
        getCurrentPosition: (ok: PositionCallback) => {
          ok({
            coords: { latitude: -6.79, longitude: 39.21, accuracy: 12 },
            timestamp: Date.parse('2026-10-26T15:01:00Z'),
          } as GeolocationPosition);
        },
      },
    });
    renderWithProviders(<FieldCheckinPage />, {
      tenantPermissions: ['tenant.site_checkin.record'],
    });
    expect(await screen.findByText('Due now')).toBeInTheDocument();
    expect(screen.getByText('A check-in is due now', { exact: false })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Check in now' }));
    await waitFor(() => {
      expect(mocks.record).toHaveBeenCalled();
    });
    expect(mocks.record.mock.calls[0]?.[0].gps).toMatchObject({
      status: 'FIX',
      latitude: -6.79,
      longitude: 39.21,
    });
    expect(mocks.record.mock.calls[0]?.[0]).not.toHaveProperty('job_site_id');
  });

  it('sends the failed GPS attempt without coordinates', async () => {
    const user = userEvent.setup();
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: {
        getCurrentPosition: (_ok: PositionCallback, fail: PositionErrorCallback) => {
          fail({ code: 1, message: 'denied' } as GeolocationPositionError);
        },
      },
    });
    mocks.record.mockResolvedValue({
      ...CHECKIN,
      gps_status: 'PERMISSION_DENIED',
      latitude: null,
      longitude: null,
      accuracy_m: null,
      distance_m: null,
      within_distance: null,
    });
    renderWithProviders(<FieldCheckinPage />, {
      tenantPermissions: ['tenant.site_checkin.record'],
    });
    await user.click(await screen.findByRole('button', { name: 'Check in now' }));
    await waitFor(() => {
      expect(mocks.record).toHaveBeenCalled();
    });
    const gps = mocks.record.mock.calls[0]?.[0].gps;
    expect(gps?.status).toBe('PERMISSION_DENIED');
    expect(gps).not.toHaveProperty('latitude');
  });
});
