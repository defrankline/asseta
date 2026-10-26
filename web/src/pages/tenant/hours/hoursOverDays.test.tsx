import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  HoursPurchaseDto,
  HoursStatementDto,
  LowBalanceAlertDto,
} from '../../../api/hoursTypes';
import type { hoursRequestService, hoursService } from '../../../api/services/hoursService';
import {
  apiRelativePath,
  hoursStatementSchema,
  lowBalanceAlertSchema,
  type hoursStatementService,
} from '../../../api/services/hoursStatementService';
import type { policyService } from '../../../api/services/policyService';
import { HOURS_ROUTES, lowBalanceAlertPath } from '../../../navigation/hoursRoutes';
import { notificationTargetPath } from '../../../notifications/center/display';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { HoursPurchaseDetailPage } from './HoursPurchaseDetailPage';
import { HoursStatementPanel } from './HoursStatementPanel';
import { LowBalanceAlertDetailPage, LowBalanceAlertsPage } from './LowBalanceAlertsPage';

const mocks = vi.hoisted(() => ({
  effective: vi.fn<typeof policyService.effective>(),
  statement: vi.fn<typeof hoursStatementService.statement>(),
  downloadPdf: vi.fn<typeof hoursStatementService.downloadPdf>(),
  listAlerts: vi.fn<typeof hoursStatementService.listLowBalanceAlerts>(),
  getAlert: vi.fn<typeof hoursStatementService.getLowBalanceAlert>(),
  saveBlob: vi.fn(),
  getPurchase: vi.fn<typeof hoursService.getPurchase>(),
  listTransfers: vi.fn<typeof hoursRequestService.listTransfers>(),
  listCancellations: vi.fn<typeof hoursRequestService.listCancellations>(),
}));
vi.mock('../../../api/services/hoursService', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  hoursService: { getPurchase: mocks.getPurchase },
  hoursRequestService: {
    listTransfers: mocks.listTransfers,
    listCancellations: mocks.listCancellations,
  },
}));
vi.mock('../../../api/services/policyService', () => ({
  policyService: { effective: mocks.effective },
}));
vi.mock('../../../api/services/hoursStatementService', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  hoursStatementService: {
    statement: mocks.statement,
    downloadPdf: mocks.downloadPdf,
    listLowBalanceAlerts: mocks.listAlerts,
    getLowBalanceAlert: mocks.getAlert,
  },
}));
vi.mock('../../../components/data/exportFile', () => ({ saveBlob: mocks.saveBlob }));

const ALERT: LowBalanceAlertDto = {
  id: 'a1',
  purchase_id: 'p1',
  purchase_number: 'HP-2026-00007',
  customer_id: 'c1',
  customer_name: 'Juma Construction',
  machine_id: 'm1',
  machine_code: 'EX-01',
  machine_name: 'Excavator',
  sequence: 1,
  threshold_hours: '5',
  remaining_hours: '4.5',
  available_hours: '4.5',
  crossed_at: '2026-10-25T10:00:00Z',
  rearmed_at: null,
  notify_customer: true,
  customer_sms_status: 'NO_PHONE',
  customer_sms_id: null,
  policy_version: 'CUSTOMER_HOURS@v4',
};

const STATEMENT: HoursStatementDto = {
  customer_id: 'c1',
  customer_name: 'Juma Construction',
  machine_id: null,
  date_from: '2026-10-01',
  date_to: '2026-10-26',
  timezone: 'Africa/Dar_es_Salaam',
  generated_at: '2026-10-26T12:00:00Z',
  pdf_path:
    '/api/v1/tenant/customers/c1/hours-statement.pdf?date_from=2026-10-01&date_to=2026-10-26',
  totals: {
    opening_balance: '10',
    bought: '20',
    activated: '20',
    used: '12.5',
    transferred_in: '0',
    transferred_out: '0',
    expired: '0',
    cancelled: '0',
    closing_balance: '17.5',
    provisional_at_close: '3',
    awaiting_activation: '0',
  },
  purchases: [
    {
      purchase_id: 'p1',
      purchase_number: 'HP-2026-00007',
      machine_id: 'm1',
      machine_code: 'EX-01',
      machine_name: 'Excavator',
      status: 'ACTIVE',
      bought_at: '2026-10-02T08:00:00Z',
      hours: '20',
      activated: '20',
      amount: '1000000',
      currency: 'TZS',
      effective_rate: '50000',
      remaining_at_close: '17.5',
      next_expiry_at: null,
      expiring_hours: '0',
      cancelled_at: null,
    },
  ],
  usage: [
    {
      day: '2026-10-25',
      job_id: 'j1',
      job_number: 'JOB-0042',
      machine_id: 'm1',
      machine_code: 'EX-01',
      machine_name: 'Excavator',
      hours: '3',
      basis: 'DAILY',
      job_running: true,
    },
  ],
  lines: [
    {
      entry_id: 'e1',
      occurred_at: '2026-10-25T20:00:00Z',
      day: '2026-10-25',
      entry_type: 'PROVISIONAL',
      hours: '-3',
      balance_after: '17.5',
      purchase_id: 'p1',
      purchase_number: 'HP-2026-00007',
      machine_id: 'm1',
      machine_code: 'EX-01',
      machine_name: 'Excavator',
      job_id: 'j1',
      job_number: 'JOB-0042',
      reason: null,
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.effective.mockResolvedValue({
    policy_type: 'CUSTOMER_HOURS',
    version_stamp: 'v1',
    values: { enabled: true },
  });
});

describe('hours over days contract', () => {
  it('validates the statement and warning payloads and strips the API base from pdf_path', () => {
    expect(hoursStatementSchema.isValidSync(STATEMENT)).toBe(true);
    expect(lowBalanceAlertSchema.isValidSync(ALERT)).toBe(true);
    expect(apiRelativePath(STATEMENT.pdf_path)).toBe(
      '/tenant/customers/c1/hours-statement.pdf?date_from=2026-10-01&date_to=2026-10-26',
    );
  });

  it('opens the purchase from a HOURS_LOW_BALANCE notification', () => {
    expect(
      notificationTargetPath(
        { entity: 'hours_purchase', id: 'p1', path: '/tenant/hours/purchases/p1' },
        { kind: 'HOURS_PURCHASE', record_id: 'p1', alert_id: 'a1' },
      ),
    ).toBe('/tenant/hours/purchases/p1');
    expect(notificationTargetPath({ entity: 'hours_purchase', id: 'p9', path: null })).toBe(
      '/tenant/hours/purchases/p9',
    );
    // Customer hours switched off: no dead link.
    expect(
      notificationTargetPath(
        null,
        { kind: 'HOURS_PURCHASE', record_id: 'p1' },
        new Set(['CUSTOMER_HOURS']),
      ),
    ).toBeNull();
  });
});

describe('HoursStatementPanel', () => {
  it('shows totals, purchases, usage and movements, and downloads the PDF', async () => {
    const user = userEvent.setup();
    mocks.statement.mockResolvedValue(STATEMENT);
    const blob = new Blob(['%PDF']);
    mocks.downloadPdf.mockResolvedValue({ blob, filename: 'hours-statement.pdf' });
    renderWithProviders(<HoursStatementPanel customerId="c1" timeZone="UTC" />, {
      tenantPermissions: ['tenant.hours.read'],
    });
    const totals = await screen.findByRole('table', { name: 'Hours statement totals' });
    expect(within(totals).getByText('Closing balance')).toBeInTheDocument();
    expect(within(totals).getByText('17.5 h')).toBeInTheDocument();
    expect(screen.getByText(/3 h are in use by running jobs/)).toBeInTheDocument();
    expect(mocks.statement).toHaveBeenCalledWith(
      'c1',
      expect.objectContaining({ machine_id: undefined, date_to: expect.any(String) as unknown }),
      expect.any(AbortSignal),
    );
    const usage = screen.getByRole('table', { name: 'Statement usage' });
    expect(within(usage).getByRole('link', { name: 'JOB-0042' })).toHaveAttribute(
      'href',
      '/tenant/jobs/j1',
    );
    expect(within(usage).getByText('Drawn that day · job still running')).toBeInTheDocument();
    const lines = screen.getByRole('table', { name: 'Statement movements' });
    expect(within(lines).getByText('Used that day (provisional)')).toBeInTheDocument();
    expect(
      within(screen.getByRole('table', { name: 'Statement purchases' })).getByRole('link', {
        name: 'HP-2026-00007',
      }),
    ).toHaveAttribute('href', '/tenant/hours/purchases/p1');
    expect(screen.getByRole('link', { name: 'Low-balance warnings' })).toHaveAttribute(
      'href',
      '/tenant/hours/low-balance-alerts?customer_id=c1',
    );
    await user.click(screen.getByRole('button', { name: 'Download PDF' }));
    await waitFor(() => {
      expect(mocks.saveBlob).toHaveBeenCalledWith(blob, 'hours-statement.pdf');
    });
    expect(mocks.downloadPdf).toHaveBeenCalledWith(STATEMENT.pdf_path);
  });

  it('refuses a period longer than 366 days without calling the API', async () => {
    const user = userEvent.setup();
    mocks.statement.mockResolvedValue(STATEMENT);
    renderWithProviders(<HoursStatementPanel customerId="c1" timeZone="UTC" />, {
      tenantPermissions: ['tenant.hours.read'],
    });
    await screen.findByRole('table', { name: 'Hours statement totals' });
    mocks.statement.mockClear();
    const from = screen.getByLabelText('From');
    await user.clear(from);
    await user.type(from, '2024-01-01');
    expect(await screen.findByText('Choose a period of at most 366 days.')).toBeInTheDocument();
    expect(mocks.statement).not.toHaveBeenCalledWith(
      'c1',
      expect.objectContaining({ date_from: '2024-01-01' }),
      expect.any(AbortSignal),
    );
  });
});

describe('Low-balance warnings', () => {
  it('lists warnings with the purchase filter from the URL and opens one', async () => {
    const user = userEvent.setup();
    mocks.listAlerts.mockResolvedValue({ items: [ALERT], total: 1, page: 1, page_size: 20 });
    mocks.getAlert.mockResolvedValue(ALERT);
    renderWithProviders(
      <Routes>
        <Route path={HOURS_ROUTES.lowBalanceAlerts} element={<LowBalanceAlertsPage />} />
        <Route path={HOURS_ROUTES.lowBalanceAlertDetail} element={<LowBalanceAlertDetailPage />} />
      </Routes>,
      {
        tenantPermissions: ['tenant.hours.read', 'tenant.policy.read'],
        route: `${HOURS_ROUTES.lowBalanceAlerts}?purchase_id=p1&armed=true`,
      },
    );
    expect(await screen.findByText('HP-2026-00007')).toBeInTheDocument();
    expect(mocks.listAlerts).toHaveBeenCalledWith(
      expect.objectContaining({
        filters: expect.objectContaining({ purchase_id: 'p1', armed: 'true' }) as unknown,
      }),
      expect.any(AbortSignal),
    );
    expect(screen.getByText('One purchase')).toBeInTheDocument();
    expect(screen.getAllByText('Still low').length).toBeGreaterThan(0);
    await user.click(screen.getByText('Juma Construction'));
    expect(
      await screen.findByRole('heading', { name: 'Low balance · HP-2026-00007' }),
    ).toBeInTheDocument();
    expect(mocks.getAlert).toHaveBeenCalledWith('a1', expect.any(AbortSignal));
    expect(screen.getByText('Not sent: the customer has no phone number')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open the purchase' })).toHaveAttribute(
      'href',
      '/tenant/hours/purchases/p1',
    );
  });

  it('shows a topped-up warning with its history', async () => {
    mocks.getAlert.mockResolvedValue({ ...ALERT, rearmed_at: '2026-10-26T09:00:00Z' });
    renderWithProviders(
      <Routes>
        <Route path={HOURS_ROUTES.lowBalanceAlertDetail} element={<LowBalanceAlertDetailPage />} />
      </Routes>,
      { tenantPermissions: ['tenant.hours.read'], route: lowBalanceAlertPath('a1') },
    );
    const history = await screen.findByRole('list', { name: 'History' });
    expect(history).toHaveTextContent('Fell to the threshold');
    expect(history).toHaveTextContent('Back above the threshold');
    expect(screen.getAllByText('Topped up since').length).toBeGreaterThan(0);
  });
});

const PURCHASE = {
  id: 'p1',
  purchase_number: 'HP-2026-00007',
  customer_id: 'c1',
  customer_kind: 'REGISTERED',
  customer_name: 'Juma Construction',
  machine_id: 'm1',
  machine_code: 'EX-01',
  machine_name: 'Excavator',
  job_site_id: null,
  hours: '20',
  currency: 'TZS',
  rate_card_id: 'rc1',
  hourly_rate: '50000',
  discount_id: null,
  discount_percent: '0',
  effective_rate: '50000',
  amount: '1000000',
  status: 'ACTIVE',
  source: 'WEB',
  note: null,
  policy_version: 'v1',
  client_id: null,
  created_at: '2026-10-02T08:00:00Z',
  created_by: null,
  cancellation_id: null,
  cancelled_at: null,
  allocations: [],
  payment: null,
  machines: [
    {
      machine_id: 'm1',
      machine_code: 'EX-01',
      machine_name: 'Excavator',
      activated: '20',
      consumed: '0',
      expired: '0',
      remaining: '17',
      reversed: '0',
      transferred_in: '0',
      transferred_out: '0',
      provisional: '3',
    },
  ],
  totals: {
    purchased: '20',
    activated: '20',
    activated_from_payments: '20',
    activated_on_credit: '0',
    awaiting_activation: '0',
    consumed: '0',
    expired: '0',
    remaining: '17',
    reversed: '0',
    transferred: '0',
    provisional: '3',
    amount_claimed_unverified: '0',
    amount_outstanding: '0',
    amount_verified: '1000000',
  },
} as HoursPurchaseDto;

describe('HoursPurchaseDetailPage (daily drawdown)', () => {
  it('shows hours in use by running jobs and links its low-balance warnings', async () => {
    mocks.getPurchase.mockResolvedValue(PURCHASE);
    const empty = { items: [], total: 0, page: 1, page_size: 100 };
    mocks.listTransfers.mockResolvedValue(empty);
    mocks.listCancellations.mockResolvedValue(empty);
    renderWithProviders(
      <Routes>
        <Route path={HOURS_ROUTES.purchaseDetail} element={<HoursPurchaseDetailPage />} />
      </Routes>,
      { tenantPermissions: ['tenant.hours.read'], route: '/tenant/hours/purchases/p1' },
    );
    const perMachine = await screen.findByRole('table', { name: 'Hours per machine' });
    expect(within(perMachine).getByText('In use by running jobs')).toBeInTheDocument();
    expect(within(perMachine).getByText('3 h')).toBeInTheDocument();
    expect(screen.getAllByText('In use by running jobs').length).toBe(2);
    expect(screen.getByRole('link', { name: 'Low-balance warnings' })).toHaveAttribute(
      'href',
      '/tenant/hours/low-balance-alerts?purchase_id=p1',
    );
  });
});
