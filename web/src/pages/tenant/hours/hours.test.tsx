import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  DiscountDto,
  HoursPurchaseDto,
  LedgerEntryDto,
  TransferDto,
} from '../../../api/hoursTypes';
import type {
  discountService,
  hoursRequestService,
  hoursService,
} from '../../../api/services/hoursService';
import type { policyService } from '../../../api/services/policyService';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { CustomerDiscountsPage } from './CustomerDiscountsPage';
import { HoursLedgerPage } from './HoursLedgerPage';
import { HoursPurchasesPage } from './HoursPurchasesPage';
import { HoursTransfersPage } from './HoursTransfersPage';
import { paidSummary } from './hoursQuote';
import {
  emptyPaymentLine,
  emptyPurchaseValues,
  followTotal,
  OVER_TOTAL_TEXT,
  paymentsExceedTotal,
  purchaseSchema,
  toPurchasePayload,
} from './purchaseForm';
import { parseHoursPolicy } from './useHoursPolicy';

const ME = '33333333-3333-4333-8333-333333333333';
const OTHER = '44444444-4444-4444-8444-444444444444';

const mocks = vi.hoisted(() => ({
  effective: vi.fn<typeof policyService.effective>(),
  listPurchases: vi.fn<typeof hoursService.listPurchases>(),
  listLedger: vi.fn<typeof hoursService.listLedger>(),
  listTransfers: vi.fn<typeof hoursRequestService.listTransfers>(),
  withdrawTransfer: vi.fn<typeof hoursRequestService.withdrawTransfer>(),
  listDiscounts: vi.fn<typeof discountService.list>(),
  decideDiscount: vi.fn<typeof discountService.decide>(),
}));
vi.mock('../../../api/services/policyService', () => ({
  policyService: { effective: mocks.effective },
}));
vi.mock('../../../api/services/hoursService', () => ({
  hoursService: { listPurchases: mocks.listPurchases, listLedger: mocks.listLedger },
  hoursRequestService: {
    listTransfers: mocks.listTransfers,
    withdrawTransfer: mocks.withdrawTransfer,
  },
  discountService: { list: mocks.listDiscounts, decide: mocks.decideDiscount },
  creditArrangementService: {},
  hoursReasonService: { search: vi.fn(), get: vi.fn() },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 }),
  },
}));
vi.mock('../../../api/services/customerService', () => ({
  customerService: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 }),
  },
}));

const POLICY = {
  enabled: true,
  walk_in_allowed: true,
  billing_modes: ['PREPAID_HOURS', 'INVOICE'],
  default_billing_mode: 'INVOICE',
  activation_basis: ['VERIFIED_PAYMENT', 'CREDIT'],
  credit_allowed: true,
  reason_code_required: false,
  max_discount_percent: '100',
};
const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 25 });

const PURCHASE: HoursPurchaseDto = {
  id: 'p1',
  purchase_number: 'HP-2026-00001',
  customer_id: 'c1',
  customer_kind: 'WALK_IN',
  customer_name: 'Juma',
  machine_id: 'm1',
  job_site_id: null,
  hours: '10',
  currency: 'TZS',
  rate_card_id: 'rc1',
  hourly_rate: '50000',
  discount_id: null,
  discount_percent: '0',
  effective_rate: '50000',
  amount: '500000',
  status: 'AWAITING_PAYMENT',
  source: 'WEB',
  note: null,
  policy_version: 'v1',
  client_id: null,
  created_at: '2026-10-20T08:00:00Z',
  created_by: ME,
  cancellation_id: null,
  cancelled_at: null,
  allocations: [],
  machines: [],
  payment: null,
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
    provisional: '0',
    refunded: '0',
    corrected: '0',
    amount_claimed_unverified: '0',
    amount_outstanding: '500000',
    amount_verified: '0',
  },
};

const discount = (over: Partial<DiscountDto>): DiscountDto => ({
  id: 'd1',
  customer_id: 'c1',
  percent: '5',
  effective_from: '2026-10-01',
  effective_to: null,
  reason: 'Loyal customer',
  reason_code_id: null,
  proposed_at: '2026-10-20T08:00:00Z',
  proposed_by: OTHER,
  status: 'PROPOSED',
  decided_at: null,
  decided_by: null,
  decision_note: null,
  revoke_reason: null,
  revoked_at: null,
  revoked_by: null,
  version: 1,
  ...over,
});

const transfer = (over: Partial<TransferDto>): TransferDto => ({
  id: 't1',
  purchase_id: 'p1',
  from_machine_id: 'm1',
  to_machine_id: 'm2',
  hours: '2',
  reason: 'Machine down',
  reason_code_id: null,
  client_id: null,
  requested_at: '2026-10-20T08:00:00Z',
  requested_by: ME,
  status: 'PENDING',
  decided_at: null,
  decided_by: null,
  decision_note: null,
  ...over,
});

beforeEach(() => {
  mocks.effective.mockResolvedValue({
    policy_type: 'CUSTOMER_HOURS',
    version_stamp: 'v1',
    values: POLICY,
  });
  mocks.listPurchases.mockResolvedValue(page([PURCHASE]));
});

describe('parseHoursPolicy', () => {
  it('reads the effective values and treats missing switches as off', () => {
    const p = parseHoursPolicy(POLICY);
    expect(p.enabled).toBe(true);
    expect(p.billingModes).toEqual(['PREPAID_HOURS', 'INVOICE']);
    expect(p.activationBasis).toContain('CREDIT');
    expect(parseHoursPolicy({}).enabled).toBe(false);
    expect(parseHoursPolicy({ billing_modes: ['BOGUS'] }).billingModes).toEqual([]);
  });
});

describe('toPurchasePayload', () => {
  it('sends a walk-in with a field cash payment in own custody and the evidence id', () => {
    const v = {
      ...emptyPurchaseValues(),
      customer_mode: 'WALK_IN' as const,
      walk_in_name: ' Juma ',
      machine_id: 'm1',
      hours: '10',
      payments: [
        {
          ...emptyPaymentLine('CASH', '50000', '2026-10-20T08:00:00Z'),
          staff_member_id: 's9',
          evidence: {
            id: 'a1',
            sha256: 'x',
            content_type: 'image/jpeg',
            size_bytes: 1,
            purpose: 'PAYMENT_EVIDENCE',
            uploaded_at: '2026-10-20T08:00:00Z',
          },
        },
      ],
    };
    const body = toPurchasePayload(v, 'client-1', { field: true });
    expect(body.customer_id).toBeNull();
    expect(body.walk_in).toEqual({ name: 'Juma', phone: null, client_id: 'client-1' });
    expect(body.payment).toBeUndefined();
    expect(body.payments).toEqual([
      {
        method: 'CASH',
        amount: '50000',
        reference: null,
        received_at: '2026-10-20T08:00:00Z',
        staff_member_id: null,
        evidence_attachment_ids: ['a1'],
      },
    ]);
  });

  it('splits the bill across methods and keeps the office custodian', () => {
    const at = '2026-10-20T08:00:00Z';
    const body = toPurchasePayload(
      {
        ...emptyPurchaseValues(),
        customer_id: 'c1',
        machine_id: 'm1',
        hours: '6',
        payments: [
          { ...emptyPaymentLine('CASH', '300000', at), staff_member_id: 's9' },
          { ...emptyPaymentLine('BANK', '270000', at), reference: ' TT-1 ' },
        ],
      },
      'client-1',
      { field: false },
    );
    expect(body.payments?.map((p) => [p.method, p.amount, p.reference, p.staff_member_id])).toEqual(
      [
        ['CASH', '300000', null, 's9'],
        ['BANK', '270000', 'TT-1', null],
      ],
    );
  });

  it('sends no payments when the opening line was removed (not paid yet)', () => {
    expect(
      toPurchasePayload(
        { ...emptyPurchaseValues(), machine_id: 'm1', hours: '1', payments: [] },
        'c',
        {
          field: true,
        },
      ).payments,
    ).toEqual([]);
  });

  it('opens with one Cash line that follows the total until typed into', () => {
    const v = emptyPurchaseValues();
    expect(v.payments).toHaveLength(1);
    expect(v.payments[0]).toMatchObject({ method: 'CASH', amount: '', follows_total: true });
    const followed = followTotal(v.payments, '570000.0000');
    expect(followed?.[0]?.amount).toBe('570000');
    expect(followTotal(followed ?? [], '570000.0000')).toBeNull();
    expect(followTotal(followed ?? [], '380000.0000')?.[0]?.amount).toBe('380000');
    expect(followTotal(followed ?? [], '')?.[0]?.amount).toBe('');
    const typed = (followed ?? []).map((l) => ({ ...l, amount: '100000', follows_total: false }));
    expect(followTotal(typed, '380000.0000')).toBeNull();
    // The followed line travels as one cash payment; follows_total is never sent.
    const body = toPurchasePayload(
      { ...v, customer_id: 'c1', machine_id: 'm1', hours: '6', payments: followed ?? [] },
      'c',
      { field: true },
    );
    expect(body.payments).toEqual([
      expect.objectContaining({ method: 'CASH', amount: '570000', reference: null }),
    ]);
    expect(body.payments?.[0]).not.toHaveProperty('follows_total');
  });
});

describe('purchaseSchema payments', () => {
  const at = '2026-10-20T08:00:00Z';
  const base = { ...emptyPurchaseValues(), customer_id: 'c1', machine_id: 'm1', hours: '6' };

  it('blocks lines adding up to more than the total', async () => {
    const v = {
      ...base,
      quote_amount: '570000.0000',
      payments: [emptyPaymentLine('CASH', '400000', at), emptyPaymentLine('CASH', '200000', at)],
    };
    expect(paymentsExceedTotal(v)).toBe(true);
    await expect(purchaseSchema.validate(v)).rejects.toThrow(OVER_TOTAL_TEXT);
    await expect(
      purchaseSchema.validate({ ...v, payments: [emptyPaymentLine('CASH', '570000', at)] }),
    ).resolves.toBeTruthy();
  });

  it('requires a reference for bank and mobile money', async () => {
    await expect(
      purchaseSchema.validate({
        ...base,
        payments: [emptyPaymentLine('MOBILE_MONEY', '1000', at)],
      }),
    ).rejects.toThrow(/Reference is required/);
  });

  it('reads field_noncash_payments, off by default', () => {
    expect(parseHoursPolicy({}).fieldNoncashPayments).toBe(false);
    expect(parseHoursPolicy({ field_noncash_payments: true }).fieldNoncashPayments).toBe(true);
  });
});

describe('paidSummary', () => {
  it('words fully paid, part paid and not paid yet', () => {
    expect(paidSummary('570000', '570000.0000', 'TZS')).toEqual({
      line: 'Paid TZS 570,000 of TZS 570,000 · Balance TZS 0',
      status: 'Fully paid',
      over: false,
    });
    expect(paidSummary('500000', '570000', 'TZS').status).toBe('Part paid (balance TZS 70,000)');
    expect(paidSummary('0', '570000', 'TZS').status).toBe('Not paid yet');
    expect(paidSummary('600000', '570000', 'TZS').over).toBe(true);
  });
});

describe('HoursPurchasesPage', () => {
  it('offers New purchase only with the permission and while customer hours are on', async () => {
    const { unmount } = renderWithProviders(<HoursPurchasesPage />, {
      tenantPermissions: ['tenant.hours.read'],
    });
    expect(await screen.findByText('HP-2026-00001')).toBeInTheDocument();
    expect(screen.getByText('Juma (walk-in)')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New purchase' })).not.toBeInTheDocument();
    unmount();
    const perms = ['tenant.hours.read', 'tenant.hours.purchase'];
    const second = renderWithProviders(<HoursPurchasesPage />, { tenantPermissions: perms });
    expect(await screen.findByRole('button', { name: 'New purchase' })).toBeInTheDocument();
    second.unmount();
    mocks.effective.mockResolvedValue({
      policy_type: 'CUSTOMER_HOURS',
      version_stamp: 'v2',
      values: { ...POLICY, enabled: false },
    });
    renderWithProviders(<HoursPurchasesPage />, { tenantPermissions: perms });
    expect(await screen.findByText(/switched off in your company policy/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New purchase' })).not.toBeInTheDocument();
  });
});

describe('CustomerDiscountsPage', () => {
  const perms = ['tenant.hours.read', 'tenant.hours.discount', 'tenant.hours.discount_approve'];

  it('disables Decide on your own proposal and lets others decide', async () => {
    const user = userEvent.setup();
    mocks.listDiscounts.mockResolvedValue(
      page([discount({ id: 'mine', proposed_by: ME }), discount({ id: 'theirs', percent: '7' })]),
    );
    mocks.decideDiscount.mockResolvedValue(discount({ id: 'theirs', status: 'APPROVED' }));
    renderWithProviders(<CustomerDiscountsPage />, { tenantPermissions: perms });
    const own = await screen.findByRole('button', {
      name: 'Decide (Someone else must decide your own request)',
    });
    expect(own).toBeDisabled();
    const rows = screen.getAllByRole('row');
    const theirs = rows.find((r) => within(r).queryByText('7 %') !== null);
    if (theirs === undefined) throw new Error('row missing');
    await user.click(within(theirs).getByRole('button', { name: 'Decide' }));
    await user.click(screen.getByRole('combobox', { name: /Decision/ }));
    await user.click(await screen.findByRole('option', { name: 'Approve' }));
    await user.click(screen.getByRole('button', { name: 'Record decision' }));
    await waitFor(() => {
      expect(mocks.decideDiscount).toHaveBeenCalledWith(
        'theirs',
        { approve: true, note: null },
        expect.any(String),
      );
    });
  });

  it('hides Propose without the propose permission', async () => {
    mocks.listDiscounts.mockResolvedValue(page([]));
    renderWithProviders(<CustomerDiscountsPage />, { tenantPermissions: ['tenant.hours.read'] });
    expect(await screen.findByText('No discounts')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Propose discount' })).not.toBeInTheDocument();
  });
});

describe('HoursTransfersPage', () => {
  it('lets only the requester withdraw a pending transfer', async () => {
    const user = userEvent.setup();
    mocks.listTransfers.mockResolvedValue(
      page([transfer({}), transfer({ id: 't2', requested_by: OTHER, hours: '3' })]),
    );
    mocks.withdrawTransfer.mockResolvedValue(transfer({ status: 'WITHDRAWN' }));
    renderWithProviders(<HoursTransfersPage />, {
      tenantPermissions: ['tenant.hours.read', 'tenant.hours.transfer'],
    });
    const buttons = await screen.findAllByRole('button', { name: 'Withdraw' });
    expect(buttons).toHaveLength(1);
    const [withdraw] = buttons;
    if (withdraw === undefined) throw new Error('missing');
    await user.click(withdraw);
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Fixed the machine');
    await user.click(screen.getByRole('button', { name: 'Withdraw request' }));
    await waitFor(() => {
      expect(mocks.withdrawTransfer).toHaveBeenCalledWith(
        't1',
        { reason: 'Fixed the machine' },
        expect.any(String),
      );
    });
  });
});

const ledgerEntry = (over: Partial<LedgerEntryDto>): LedgerEntryDto => ({
  id: 'e1',
  purchase_id: 'aaaaaaaa-0000-4000-8000-000000000001',
  purchase_number: 'HP-2026-00001',
  customer_id: 'c1',
  customer_name: 'Juma',
  machine_id: 'm1',
  machine_code: 'EXC-1',
  machine_name: 'Excavator',
  entry_type: 'CONSUMED',
  hours: '4',
  signed_hours: '-4',
  occurred_at: '2026-10-20T08:00:00Z',
  activation_source: null,
  expires_at: null,
  payment_id: null,
  job_id: 'bbbbbbbb-0000-4000-8000-000000000002',
  job_number: 'P-1',
  allocation_id: null,
  transfer_id: null,
  cancellation_id: null,
  reason: null,
  policy_version: null,
  created_by: null,
  created_at: '2026-10-20T08:00:00Z',
  ...over,
});

describe('HoursLedgerPage', () => {
  it('links each entry to its purchase and job by number, short id when unnamed', async () => {
    mocks.listLedger.mockResolvedValue(
      page([ledgerEntry({}), ledgerEntry({ id: 'e2', purchase_number: null, job_number: null })]),
    );
    renderWithProviders(<HoursLedgerPage />, { tenantPermissions: ['tenant.hours.read'] });
    const purchase = await screen.findByRole('link', { name: 'HP-2026-00001' });
    expect(purchase).toHaveAttribute('href', expect.stringContaining('aaaaaaaa-0000'));
    expect(screen.getByRole('link', { name: 'P-1' })).toHaveAttribute(
      'href',
      expect.stringContaining('bbbbbbbb-0000'),
    );
    expect(screen.getByRole('link', { name: 'aaaaaaaa…' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'bbbbbbbb…' })).toBeInTheDocument();
  });
});
