import { screen, waitFor, within } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import { ApiError } from '../../../api/ApiError';
import { PlatformInvoicingServiceContext } from '../../../api/services/platformInvoicingService';
import type { TenantDto } from '../../../api/types';
import { typeIsoDate } from '../../../test/dateInput';
import {
  fakePlatformInvoicingService,
  type FakePlatformInvoicingService,
} from '../../../test/fakePlatformInvoicingService';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { InvoicesPage } from '../invoices/InvoicesPage';
import {
  EMPTY_LINE,
  emptyRaiseInvoice,
  raiseInvoiceSchema,
  toRaiseBody,
  type RaiseLineValues,
} from './raiseInvoiceForm';

const TENANT = { id: 'tenant-1', display_name: 'Kilimanjaro Plant Hire' } as TenantDto;

vi.mock('../shared/platformLookups', () => ({
  tenantId: (t: TenantDto) => t.id,
  tenantLabel: (t: TenantDto) => t.display_name,
  searchTenants: () => Promise.resolve([TENANT]),
  resolveTenant: () => Promise.resolve(TENANT),
}));
const invoiceList = vi.hoisted(() => vi.fn());
vi.mock('../../../api/services/platformInvoiceService', () => ({
  platformInvoiceService: { list: invoiceList },
}));

let fake: FakePlatformInvoicingService;

function renderInvoices(permissions: string[]) {
  return renderWithProviders(
    <PlatformInvoicingServiceContext.Provider value={fake}>
      <Routes>
        <Route path="/platform/invoices" element={<InvoicesPage />} />
        <Route path="/platform/invoices/:id" element={<p>Invoice details page</p>} />
      </Routes>
    </PlatformInvoicingServiceContext.Provider>,
    { permissions, route: '/platform/invoices' },
  );
}

async function pickTenant(user: UserEvent) {
  const dialog = screen.getByRole('dialog');
  await user.click(within(dialog).getByRole('combobox', { name: /Tenant/ }));
  await user.click(await screen.findByRole('option', { name: 'Kilimanjaro Plant Hire' }));
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByRole('region', { name: 'Line 1' });
}

async function pickItem(user: UserEvent, line: HTMLElement, name: RegExp) {
  await user.click(within(line).getByRole('combobox', { name: /Catalog item/ }));
  await user.click(await screen.findByRole('option', { name }));
}

beforeEach(() => {
  fake = fakePlatformInvoicingService();
  invoiceList.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
});

describe('Invoices list', () => {
  it('hides Raise invoice without platform.invoice.raise and filters by kind', async () => {
    const user = userEvent.setup();
    renderInvoices([P.platformInvoiceRead]);
    expect(await screen.findByText('No invoices')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Raise invoice' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: 'Kind' }));
    await user.click(screen.getByRole('option', { name: 'Ad hoc' }));
    await waitFor(() => {
      expect(invoiceList).toHaveBeenLastCalledWith(
        expect.objectContaining({ kind: 'AD_HOC' }),
        expect.any(AbortSignal),
      );
    });
  });
});

describe('Raise invoice stepper', () => {
  it('validates terms and lines before the Review step', async () => {
    const user = userEvent.setup();
    renderInvoices([P.platformInvoiceRead, P.platformInvoiceRaise]);
    await user.click(await screen.findByRole('button', { name: 'Raise invoice' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Choose a tenant')).toBeInTheDocument();
    await pickTenant(user);

    const line = screen.getByRole('region', { name: 'Line 1' });
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await within(line).findByText('Choose a catalog item')).toBeInTheDocument();

    // Server search by the typed text; options show type and list prices.
    await user.click(within(line).getByRole('combobox', { name: /Catalog item/ }));
    expect(await screen.findByRole('option', { name: /SETUP · On-site setup/ })).toBeVisible();
    expect(fake.listProducts).toHaveBeenLastCalledWith(
      { page: 1, page_size: 20, q: '' },
      expect.any(AbortSignal),
    );
    await user.click(screen.getByRole('option', { name: /SMS-5K/ }));
    await user.clear(within(line).getByRole('textbox', { name: /Quantity/ }));
    await user.type(within(line).getByRole('textbox', { name: /Quantity/ }), '1.5');
    await user.clear(within(line).getByRole('textbox', { name: /Discount %/ }));
    await user.type(within(line).getByRole('textbox', { name: /Discount %/ }), '120');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await within(line).findByText('SMS bundles are sold in whole units')).toBeVisible();
    expect(within(line).getByText('Discount % must be between 0 and 100')).toBeVisible();

    // A subscription fee only takes the billing period start.
    await pickItem(user, line, /SUB-FEE/);
    expect(within(line).queryByRole('textbox', { name: /Quantity/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(
      await within(line).findByText('Period start is required for a subscription fee'),
    ).toBeVisible();
    expect(screen.queryByRole('region', { name: 'Invoice preview' })).not.toBeInTheDocument();
  });

  it('shows server-computed totals on Review and submits decimal strings exactly', async () => {
    const user = userEvent.setup();
    renderInvoices([P.platformInvoiceRead, P.platformInvoiceRaise]);
    await user.click(await screen.findByRole('button', { name: 'Raise invoice' }));
    await pickTenant(user);

    const first = screen.getByRole('region', { name: 'Line 1' });
    await pickItem(user, first, /SMS-5K/);
    expect(within(first).getByText(/SMS credits are added to the tenant SMS wallet/)).toBeVisible();
    await user.clear(within(first).getByRole('textbox', { name: /Quantity/ }));
    await user.type(within(first).getByRole('textbox', { name: /Quantity/ }), '3');
    await user.type(within(first).getByRole('textbox', { name: /Unit price/ }), '33333.335');
    await user.clear(within(first).getByRole('textbox', { name: /Discount %/ }));
    await user.type(within(first).getByRole('textbox', { name: /Discount %/ }), '10');

    await user.click(screen.getByRole('button', { name: 'Add line' }));
    const second = screen.getByRole('region', { name: 'Line 2' });
    await pickItem(user, second, /SUB-FEE/);
    await typeIsoDate(user, /Billing period start/, '2099-01-01', second);
    await user.click(screen.getByRole('button', { name: 'Next' }));

    const review = await screen.findByRole('region', { name: 'Invoice preview' });
    // 3 × 33333.335 = 100000.005, −10 % = 90000.0045 → 90000.00; + 150000 subscription.
    // Subtotal and total (no discount_total/tax in this fake server).
    expect(within(review).getAllByText('TZS 240,000.00')).toHaveLength(2);
    expect(within(review).getByText('TZS 90,000.00')).toBeInTheDocument();
    expect(within(review).getByText('Kilimanjaro Plant Hire')).toBeInTheDocument();
    expect(fake.previewInvoice).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole('button', { name: 'Raise invoice' }));
    await waitFor(() => {
      expect(fake.raiseInvoice).toHaveBeenCalledTimes(1);
    });
    const [body, key] = fake.raiseInvoice.mock.calls[0] ?? [];
    expect(typeof key).toBe('string');
    expect(body).toEqual({
      tenant_id: 'tenant-1',
      currency: null,
      due_date: null,
      notes: null,
      lines: [
        {
          product_id: 'prod-sms',
          quantity: '3',
          unit_price: '33333.335',
          discount_percent: '10',
          period_start: null,
          description: null,
        },
        {
          product_id: 'prod-sub',
          quantity: '1',
          unit_price: null,
          discount_percent: '0',
          period_start: '2099-01-01',
          description: null,
        },
      ],
    });
    expect(await screen.findByText('Invoice details page')).toBeInTheDocument();
    expect(screen.getByText('Invoice AST-2026-0000042 raised.')).toBeInTheDocument();
  });

  it('shows a preview refusal such as PERIOD_ALREADY_BILLED with its hint', async () => {
    const user = userEvent.setup();
    fake.previewInvoice.mockRejectedValue(
      new ApiError({
        status: 409,
        code: 'PERIOD_ALREADY_BILLED',
        message: 'Period starting 2099-01-01 is already invoiced',
        correlationId: 'pb',
      }),
    );
    renderInvoices([P.platformInvoiceRead, P.platformInvoiceRaise]);
    await user.click(await screen.findByRole('button', { name: 'Raise invoice' }));
    await pickTenant(user);
    const line = screen.getByRole('region', { name: 'Line 1' });
    await pickItem(user, line, /SUB-FEE/);
    await typeIsoDate(user, /Billing period start/, '2099-01-01', line);
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText(/PERIOD_ALREADY_BILLED: Period starting/)).toBeVisible();
    expect(screen.getByText(/void that invoice first/)).toBeVisible();
  });
});

describe('raiseInvoiceForm', () => {
  const service: RaiseLineValues = {
    ...EMPTY_LINE,
    product_id: 'prod-setup',
    product_type: 'SERVICE',
    priced_in: ['USD'],
  };
  const valid = { ...emptyRaiseInvoice('tenant-1'), lines: [service] };

  it('requires a negotiated price when the item has no list price in the invoice currency', () => {
    expect(() =>
      raiseInvoiceSchema.validateSync({ ...valid, currency: 'TZS' }, { abortEarly: false }),
    ).toThrow('This item has no TZS list price: enter a negotiated unit price.');
    expect(raiseInvoiceSchema.isValidSync({ ...valid, currency: 'USD' })).toBe(true);
    expect(
      raiseInvoiceSchema.isValidSync({
        ...valid,
        currency: 'TZS',
        lines: [{ ...service, unit_price: '600000' }],
      }),
    ).toBe(true);
  });

  it('allows one subscription period per invoice', () => {
    const sub: RaiseLineValues = {
      ...EMPTY_LINE,
      product_id: 'prod-sub',
      product_type: 'SUBSCRIPTION_FEE',
      period_start: '2099-01-01',
    };
    expect(() => raiseInvoiceSchema.validateSync({ ...valid, lines: [sub, sub] })).toThrow(
      'DUPLICATE_PERIOD_LINE',
    );
  });

  it('defaults currency and due date to the server and keeps decimals as typed', () => {
    const body = toRaiseBody({
      ...valid,
      notes: '  Q4 top-up ',
      lines: [{ ...service, unit_price: ' 0.1000 ', discount_percent: '' }],
    });
    expect(body).toMatchObject({ currency: null, due_date: null, notes: 'Q4 top-up' });
    expect(body.lines[0]).toMatchObject({
      unit_price: '0.1000',
      discount_percent: '0',
      period_start: null,
    });
  });
});
