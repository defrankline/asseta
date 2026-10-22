import { vi } from 'vitest';
import { ApiError } from '../api/ApiError';
import type { PlatformInvoicingService } from '../api/services/platformInvoicingService';
import type {
  AdHocInvoiceIn,
  InvoiceDto,
  InvoiceLineDto,
  PaymentDto,
  ProductDto,
  SmsWalletDto,
  SmsWalletEntryDto,
} from '../api/types';
import { multiplyDecimals, roundDecimal, sumDecimals } from '../utils/money';

export const TENANT_ID = 'tenant-1';

const product = (overrides: Partial<ProductDto>): ProductDto => ({
  id: 'p',
  code: 'P',
  name: 'Product',
  description: null,
  product_type: 'SERVICE',
  prices: {},
  sms_credits: null,
  taxable: true,
  is_active: true,
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
  deactivated_at: null,
  deactivation_reason: null,
  version: 1,
  ...overrides,
});

export const SUB_FEE = product({
  id: 'prod-sub',
  code: 'SUB-FEE',
  name: 'Subscription fee',
  product_type: 'SUBSCRIPTION_FEE',
});
export const SMS_5K = product({
  id: 'prod-sms',
  code: 'SMS-5K',
  name: 'SMS bundle 5,000',
  product_type: 'SMS_BUNDLE',
  prices: { TZS: '100000.0000' },
  sms_credits: 5000,
  version: 4,
});
export const SETUP_USD = product({
  id: 'prod-setup',
  code: 'SETUP',
  name: 'On-site setup',
  prices: { USD: '250.0000' },
});

const notFound = () =>
  new ApiError({ status: 404, code: 'NOT_FOUND', message: 'Not found.', correlationId: 'nf' });
const stale = () =>
  new ApiError({ status: 409, code: 'STALE_VERSION', message: 'Changed.', correlationId: 'sv' });

function line(overrides: Partial<InvoiceLineDto>): InvoiceLineDto {
  return {
    line_no: 1,
    line_type: 'SERVICE',
    description: 'Line',
    machine_id: null,
    quantity: '1',
    unit_price: '0.00',
    amount: '0.00',
    service_from: null,
    service_to: null,
    id: null,
    product_id: null,
    sms_credits: null,
    payable: null,
    paid: null,
    fulfilment_status: null,
    ...overrides,
  };
}

/** Plays the server for previews: amount = qty × unit × (1 − discount%), 2 dp; no tax. */
export function computePreview(body: AdHocInvoiceIn, catalog: readonly ProductDto[]): InvoiceDto {
  const currency = body.currency ?? 'TZS';
  const lines = body.lines.map((l, i) => {
    const p = catalog.find((c) => c.id === l.product_id);
    if (p?.product_type === 'SUBSCRIPTION_FEE') {
      return line({
        line_no: i + 1,
        line_type: 'SUBSCRIPTION_FEE',
        description: `Subscription ${String(l.period_start)}`,
        unit_price: '150000.00',
        amount: '150000.00',
        service_from: l.period_start ?? null,
        service_to: '2099-01-31',
      });
    }
    const unit = String(l.unit_price ?? p?.prices[currency] ?? '0');
    const gross = multiplyDecimals(String(l.quantity), unit);
    const discount = multiplyDecimals(multiplyDecimals(gross, String(l.discount_percent)), '0.01');
    return line({
      line_no: i + 1,
      line_type: p?.product_type ?? 'SERVICE',
      description: l.description ?? p?.name ?? '?',
      quantity: String(l.quantity),
      unit_price: roundDecimal(unit, 2),
      amount: roundDecimal(sumDecimals([gross, `-${discount}`]), 2),
      sms_credits: p?.sms_credits == null ? null : p.sms_credits,
    });
  });
  const total = roundDecimal(sumDecimals(['0', ...lines.map((l) => l.amount)]), 2);
  return makeInvoice({
    id: null,
    invoice_number: null,
    status: null,
    issued_at: null,
    kind: 'AD_HOC',
    currency,
    due_date: body.due_date ?? '2099-02-14',
    lines,
    subtotal: total,
    discount_total: '0.00',
    tax_total: '0.00',
    total,
    amount_paid: '0.00',
    balance: total,
    notes: body.notes ?? null,
  });
}

export function makeInvoice(overrides: Partial<InvoiceDto> = {}): InvoiceDto {
  return {
    id: 'inv-1',
    invoice_number: 'AST-2026-0000007',
    tenant_id: TENANT_ID,
    kind: 'AD_HOC',
    status: 'PARTIALLY_PAID',
    period_start: '2026-11-01',
    period_end: '2026-11-30',
    due_date: '2026-11-05',
    issued_at: '2026-10-20T08:00:00Z',
    currency: 'TZS',
    enrolled_assets: 0,
    billable_assets: 0,
    subtotal: '350000.00',
    discount_total: '0.00',
    tax_total: '0.00',
    total: '350000.00',
    amount_paid: '100000.00',
    credits_applied: '0.00',
    balance: '250000.00',
    notes: null,
    voided_at: null,
    void_reason: null,
    lines: [
      line({
        id: 'l-sms',
        line_no: 1,
        line_type: 'SMS_BUNDLE',
        description: 'SMS bundle 5,000 (10,000 SMS credits)',
        quantity: '2',
        unit_price: '100000.00',
        amount: '200000.00',
        product_id: SMS_5K.id,
        sms_credits: 10000,
        payable: '200000.00',
        paid: '100000.00',
      }),
      line({
        id: 'l-sub',
        line_no: 2,
        line_type: 'SUBSCRIPTION_FEE',
        description: 'Subscription November',
        unit_price: '150000.00',
        amount: '150000.00',
        product_id: SUB_FEE.id,
        service_from: '2026-11-01',
        service_to: '2026-11-30',
        payable: '150000.00',
        paid: '0.00',
      }),
    ],
    ...overrides,
  };
}

export function makePlatformPayment(overrides: Partial<PaymentDto> = {}): PaymentDto {
  return {
    id: 'pay-1',
    invoice_id: null,
    tenant_id: TENANT_ID,
    amount: '100000.00',
    currency: 'TZS',
    method: 'MOBILE_MONEY',
    reference: 'MPESA-QX81',
    received_on: '2026-10-21',
    status: 'VERIFIED',
    recorded_at: '2026-10-21T09:30:00Z',
    decided_at: '2026-10-21T10:00:00Z',
    decision_note: 'ok',
    unallocated: '0.00',
    allocations: [
      {
        id: 'al-1',
        invoice_id: 'inv-1',
        line_id: 'l-sms',
        amount: '100000.00',
        created_at: '2026-10-21T10:00:00Z',
        released_at: null,
        release_reason: null,
      },
    ],
    ...overrides,
  };
}

export const WALLET: SmsWalletDto = {
  tenant_id: TENANT_ID,
  balance: 420,
  low_balance_threshold: 500,
  recent_entries: [],
};

export const LEDGER: SmsWalletEntryDto[] = [
  {
    id: 'led-2',
    entry_type: 'SMS_DEBIT',
    credits: -3,
    balance_after: 420,
    reference_type: 'sms_delivery',
    reference_id: 'd-1',
    note: null,
    created_at: '2026-10-21T10:00:00Z',
  },
  {
    id: 'led-1',
    entry_type: 'BUNDLE_CREDIT',
    credits: 5000,
    balance_after: 423,
    reference_type: 'platform_line_fulfilment',
    reference_id: 'f-1',
    note: 'AST-2026-0000007 line 1: SMS bundle 5,000',
    created_at: '2026-10-20T09:00:00Z',
  },
];

/** In-memory PlatformInvoicingService; every method is a `vi.fn`. */
export function fakePlatformInvoicingService(catalog: ProductDto[] = [SUB_FEE, SMS_5K, SETUP_USD]) {
  const store = {
    catalog: [...catalog],
    invoice: makeInvoice(),
    payments: [makePlatformPayment()],
  };
  const find = (id: string) => store.catalog.find((c) => c.id === id);
  const save = (item: ProductDto) => {
    store.catalog = store.catalog.map((c) => (c.id === item.id ? item : c));
    return item;
  };
  return {
    store,
    listProducts: vi.fn<PlatformInvoicingService['listProducts']>((query) => {
      const q = query.q?.toLowerCase() ?? '';
      const items = store.catalog
        .filter((c) => query.include_inactive === true || c.is_active)
        .filter((c) => query.product_type === undefined || c.product_type === query.product_type)
        .filter((c) => q === '' || `${c.code} ${c.name}`.toLowerCase().includes(q));
      return Promise.resolve({ items, total: items.length, page: 1, page_size: query.page_size });
    }),
    getProduct: vi.fn<PlatformInvoicingService['getProduct']>((id) => {
      const item = find(id);
      return item === undefined ? Promise.reject(notFound()) : Promise.resolve(item);
    }),
    createProduct: vi.fn<PlatformInvoicingService['createProduct']>((body) => {
      const item = product({
        ...body,
        id: `prod-${String(store.catalog.length + 1)}`,
        description: body.description ?? null,
        prices: body.prices as Record<string, string>,
        sms_credits: body.sms_credits ?? null,
        taxable: body.taxable,
      });
      store.catalog.push(item);
      return Promise.resolve(item);
    }),
    updateProduct: vi.fn<PlatformInvoicingService['updateProduct']>((id, body) => {
      const item = find(id);
      if (item === undefined) return Promise.reject(notFound());
      if (item.version !== body.version) return Promise.reject(stale());
      return Promise.resolve(
        save({
          ...item,
          name: body.name,
          description: body.description ?? null,
          version: item.version + 1,
        }),
      );
    }),
    deactivateProduct: vi.fn<PlatformInvoicingService['deactivateProduct']>((id, body) => {
      const item = find(id);
      if (item === undefined) return Promise.reject(notFound());
      return Promise.resolve(
        save({
          ...item,
          is_active: false,
          deactivated_at: '2026-10-21T12:00:00Z',
          deactivation_reason: body.reason,
          version: item.version + 1,
        }),
      );
    }),
    reactivateProduct: vi.fn<PlatformInvoicingService['reactivateProduct']>((id) => {
      const item = find(id);
      if (item === undefined) return Promise.reject(notFound());
      return Promise.resolve(save({ ...item, is_active: true, deactivated_at: null }));
    }),
    previewInvoice: vi.fn<PlatformInvoicingService['previewInvoice']>((body) =>
      Promise.resolve(computePreview(body, store.catalog)),
    ),
    raiseInvoice: vi.fn<PlatformInvoicingService['raiseInvoice']>((body) => {
      const p = computePreview(body, store.catalog);
      return Promise.resolve({
        ...p,
        id: 'inv-new',
        invoice_number: 'AST-2026-0000042',
        status: 'ISSUED',
        issued_at: '2026-10-22T08:00:00Z',
      });
    }),
    getInvoice: vi.fn<PlatformInvoicingService['getInvoice']>((id) =>
      id === store.invoice.id ? Promise.resolve(store.invoice) : Promise.reject(notFound()),
    ),
    voidInvoice: vi.fn<PlatformInvoicingService['voidInvoice']>((_id, body) => {
      store.invoice = {
        ...store.invoice,
        status: 'VOIDED',
        void_reason: body.reason,
        voided_at: '2026-10-21T12:00:00Z',
        balance: '0.00',
        amount_paid: '0.00',
        lines: store.invoice.lines.map((l) =>
          l.line_type === 'SMS_BUNDLE' ? { ...l, fulfilment_status: 'REVERSAL_FLAGGED' } : l,
        ),
      };
      return Promise.resolve(store.invoice);
    }),
    listTenantPayments: vi.fn<PlatformInvoicingService['listTenantPayments']>(() =>
      Promise.resolve(store.payments),
    ),
    allocatePayment: vi.fn<PlatformInvoicingService['allocatePayment']>((id) => {
      const p = store.payments.find((x) => x.id === id);
      return p === undefined ? Promise.reject(notFound()) : Promise.resolve(p);
    }),
    getSmsWallet: vi.fn<PlatformInvoicingService['getSmsWallet']>(() => Promise.resolve(WALLET)),
    listSmsWalletEntries: vi.fn<PlatformInvoicingService['listSmsWalletEntries']>((_t, query) =>
      Promise.resolve({
        items: LEDGER,
        total: LEDGER.length,
        page: query.page,
        page_size: query.page_size,
      }),
    ),
  } satisfies PlatformInvoicingService & { store: typeof store };
}

export type FakePlatformInvoicingService = ReturnType<typeof fakePlatformInvoicingService>;
