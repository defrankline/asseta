import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type {
  CreditInvoiceDto,
  CreditRejectionDto,
  HoursPurchaseDto,
} from '../../../api/hoursTypes';
import type { creditInvoiceService } from '../../../api/services/creditInvoiceService';
import { hoursPurchaseSchema } from '../../../api/services/hoursSchemas';
import type { hoursRequestService, hoursService } from '../../../api/services/hoursService';
import type { policyService } from '../../../api/services/policyService';
import { HOURS_ROUTES } from '../../../navigation/hoursRoutes';
import { makeMe } from '../../../test/fixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { CreditInvoiceDetailPage } from './creditInvoices/CreditInvoiceDetailPage';
import { HoursPurchaseDetailPage } from './HoursPurchaseDetailPage';

const ME = makeMe().user_id;
const SELLER = '44444444-4444-4444-8444-444444444444';
const READ = 'tenant.hours.read';
const CREDIT = 'tenant.hours.credit_activate';

const mocks = vi.hoisted(() => ({
  effective: vi.fn<typeof policyService.effective>(),
  getPurchase: vi.fn<typeof hoursService.getPurchase>(),
  rejectCredit: vi.fn<typeof hoursService.rejectCredit>(),
  listTransfers: vi.fn<typeof hoursRequestService.listTransfers>(),
  listCancellations: vi.fn<typeof hoursRequestService.listCancellations>(),
  getInvoice: vi.fn<typeof creditInvoiceService.get>(),
}));
vi.mock('../../../api/services/hoursService', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  hoursService: { getPurchase: mocks.getPurchase, rejectCredit: mocks.rejectCredit },
  hoursRequestService: {
    listTransfers: mocks.listTransfers,
    listCancellations: mocks.listCancellations,
  },
}));
vi.mock('../../../api/services/creditInvoiceService', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  creditInvoiceService: { get: mocks.getInvoice },
}));
vi.mock('../../../api/services/policyService', () => ({
  policyService: { effective: mocks.effective },
}));

const REJECTION: CreditRejectionDto = {
  rejected_at: '2026-11-17T09:00:00Z',
  rejected_by: ME,
  rejected_by_name: 'Neema Owner',
  reason: 'Customer already owes too much',
  hours: '6',
  amount: '510000',
};

const SUMMARY = {
  id: 'i1',
  invoice_number: 'CI-2026-00001',
  amount: '510000',
  paid: '0',
  balance: '510000',
  due_date: '2026-12-17',
  status: 'UNPAID' as const,
  overdue: false,
  rejection: null,
};

const PURCHASE = {
  id: 'p1',
  purchase_number: 'HP-2026-00007',
  customer_id: 'c1',
  customer_kind: 'REGISTERED',
  customer_name: 'Juma Construction',
  machine_id: 'm1',
  job_site_id: null,
  hours: '10',
  currency: 'TZS',
  rate_card_id: 'rc1',
  hourly_rate: '85000',
  discount_id: null,
  discount_percent: '0',
  effective_rate: '85000',
  amount: '850000',
  status: 'AWAITING_PAYMENT',
  source: 'WEB',
  note: null,
  policy_version: 'v1',
  client_id: null,
  created_at: '2026-11-17T08:00:00Z',
  created_by: SELLER,
  cancellation_id: null,
  cancelled_at: null,
  allocations: [],
  payment: null,
  machines: [],
  credit_amount: '510000',
  credit_invoice: SUMMARY,
  credit_status: 'AWAITING_ACTIVATION',
  credit_rejection: null,
  totals: {
    purchased: '10',
    activated: '0',
    activated_from_payments: '0',
    activated_on_credit: '0',
    awaiting_activation: '10',
    consumed: '0',
    expired: '0',
    remaining: '0',
    reversed: '0',
    transferred: '0',
    refunded: '0',
    corrected: '0',
    amount_claimed_unverified: '340000',
    amount_outstanding: '850000',
    amount_verified: '0',
  },
} as HoursPurchaseDto;

const INVOICE: CreditInvoiceDto = {
  ...SUMMARY,
  purchase_id: 'p1',
  purchase_number: 'HP-2026-00007',
  customer_id: 'c1',
  customer_name: 'Juma Construction',
  machine_id: 'm1',
  currency: 'TZS',
  hours: '6',
  unit_price: '85000',
  paid_verified: '0',
  payment_terms_days: 30,
  issued_at: '2026-11-17T08:00:00Z',
  days_overdue: 0,
  created_by: SELLER,
  created_by_name: 'Asha Seller',
  payments: [],
};

function openPurchase(perms: string[]) {
  renderWithProviders(
    <Routes>
      <Route path={HOURS_ROUTES.purchaseDetail} element={<HoursPurchaseDetailPage />} />
    </Routes>,
    { tenantPermissions: perms, route: '/tenant/hours/purchases/p1' },
  );
}

function openInvoice(perms: string[]) {
  renderWithProviders(
    <Routes>
      <Route path={HOURS_ROUTES.creditInvoiceDetail} element={<CreditInvoiceDetailPage />} />
    </Routes>,
    { tenantPermissions: perms, route: '/tenant/hours/credit-invoices/i1' },
  );
}

beforeEach(() => {
  mocks.effective.mockResolvedValue({
    policy_type: 'CUSTOMER_HOURS',
    version_stamp: 'v1',
    values: {
      enabled: true,
      credit_allowed: true,
      activation_basis: ['VERIFIED_PAYMENT', 'CREDIT'],
    },
  });
  const empty = { items: [], total: 0, page: 1, page_size: 100 };
  mocks.listTransfers.mockResolvedValue(empty);
  mocks.listCancellations.mockResolvedValue(empty);
  mocks.getPurchase.mockReset().mockResolvedValue(PURCHASE);
  mocks.getInvoice.mockReset().mockResolvedValue(INVOICE);
  mocks.rejectCredit.mockReset().mockResolvedValue({
    ...PURCHASE,
    credit_status: 'REJECTED',
    credit_rejection: REJECTION,
    credit_invoice: { ...SUMMARY, status: 'CANCELLED', balance: '0', rejection: REJECTION },
  });
});

describe('Reject credit on the order', () => {
  it('sits next to Activate on credit and needs a reason', async () => {
    const user = userEvent.setup();
    openPurchase([READ, CREDIT]);
    expect(await screen.findByRole('button', { name: 'Activate on credit' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reject credit' }));
    expect(screen.getByText(/Juma Construction: TZS/)).toBeInTheDocument();
    const submit = screen.getAllByRole('button', { name: 'Reject credit' }).at(-1) as HTMLElement;
    await user.click(submit);
    expect(await screen.findByText('A reason is required')).toBeInTheDocument();
    expect(mocks.rejectCredit).not.toHaveBeenCalled();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), '  Customer already owes  ');
    await user.click(submit);
    await waitFor(() => {
      expect(mocks.rejectCredit).toHaveBeenCalled();
    });
    const [id, body] = mocks.rejectCredit.mock.calls[0] ?? [];
    expect(id).toBe('p1');
    expect(body).toEqual({ reason: 'Customer already owes' });
    expect(
      await screen.findByText(
        'Credit rejected; its invoice is cancelled and the seller is told why.',
      ),
    ).toBeInTheDocument();
  });

  it('is hidden for the seller and without the permission', async () => {
    mocks.getPurchase.mockResolvedValue({ ...PURCHASE, created_by: ME });
    openPurchase([READ, CREDIT]);
    expect(await screen.findByRole('button', { name: 'Activate on credit' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject credit' })).not.toBeInTheDocument();
  });

  it('is hidden without tenant.hours.credit_activate', async () => {
    openPurchase([READ]);
    expect(await screen.findByText('HP-2026-00007')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject credit' })).not.toBeInTheDocument();
  });

  it('explains a refusal in plain words', async () => {
    mocks.rejectCredit.mockRejectedValue(
      new ApiError({
        status: 422,
        code: 'CREDIT_INVOICE_HAS_PAYMENTS',
        message: 'x',
        correlationId: null,
      }),
    );
    const user = userEvent.setup();
    openPurchase([READ, CREDIT]);
    await user.click(await screen.findByRole('button', { name: 'Reject credit' }));
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Too much owed');
    await user.click(
      screen.getAllByRole('button', { name: 'Reject credit' }).at(-1) as HTMLElement,
    );
    expect(
      await screen.findByText(/Payments are already recorded on the credit invoice/),
    ).toBeInTheDocument();
  });

  it('shows a rejected credit: who, when, why; no credit actions left', async () => {
    mocks.getPurchase.mockResolvedValue({
      ...PURCHASE,
      status: 'CREDIT_REJECTED',
      credit_status: 'REJECTED',
      credit_rejection: REJECTION,
      credit_invoice: { ...SUMMARY, status: 'CANCELLED', balance: '0', rejection: REJECTION },
      totals: { ...PURCHASE.totals, awaiting_activation: '4' },
    });
    openPurchase([READ, CREDIT]);
    expect(await screen.findByText('Credit not approved')).toBeInTheDocument();
    expect(screen.getByText(/Customer already owes too much/)).toBeInTheDocument();
    expect(screen.getAllByText('Cancelled').length).toBeGreaterThan(0);
    expect(screen.getByText('Credit rejected')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject credit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Activate on credit' })).not.toBeInTheDocument();
  });
});

describe('Reject credit on the credit invoice', () => {
  it('is offered on an unpaid invoice of someone else’s sale and rejects its order’s credit', async () => {
    const user = userEvent.setup();
    openInvoice([READ, CREDIT]);
    await user.click(await screen.findByRole('button', { name: 'Reject credit' }));
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Not trusted yet');
    await user.click(
      screen.getAllByRole('button', { name: 'Reject credit' }).at(-1) as HTMLElement,
    );
    await waitFor(() => {
      expect(mocks.rejectCredit).toHaveBeenCalledWith(
        'p1',
        { reason: 'Not trusted yet' },
        expect.any(String),
      );
    });
  });

  it('is hidden for the seller of the order', async () => {
    mocks.getInvoice.mockResolvedValue({ ...INVOICE, created_by: ME });
    openInvoice([READ, CREDIT]);
    expect(await screen.findByText('Hours on credit')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject credit' })).not.toBeInTheDocument();
  });

  it('shows a CANCELLED invoice with the rejection reason', async () => {
    mocks.getInvoice.mockResolvedValue({
      ...INVOICE,
      status: 'CANCELLED',
      balance: '0',
      rejection: REJECTION,
    });
    openInvoice([READ, CREDIT]);
    expect(
      await screen.findByText('This invoice is cancelled: its credit was not approved.'),
    ).toBeInTheDocument();
    expect(screen.getByText(/Customer already owes too much/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject credit' })).not.toBeInTheDocument();
  });
});

describe('purchase contract', () => {
  it('accepts the credit status, the rejection and the CREDIT_REJECTED order status', () => {
    const parsed = hoursPurchaseSchema.validateSync({
      ...PURCHASE,
      status: 'CREDIT_REJECTED',
      credit_status: 'REJECTED',
      credit_rejection: REJECTION,
    });
    expect(parsed.credit_rejection?.reason).toBe('Customer already owes too much');
    expect(() =>
      hoursPurchaseSchema.validateSync({ ...PURCHASE, credit_status: 'MAYBE' }),
    ).toThrow();
  });
});
