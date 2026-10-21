import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../../access/permissionCodes';
import { ApiError } from '../../../../api/ApiError';
import type { customerService } from '../../../../api/services/customerService';
import type {
  customerPaymentService,
  hireInvoiceService,
} from '../../../../api/services/financeService';
import { CUSTOMER, ME, makeInvoice, makePayment, page } from '../../../../test/financeFixtures';
import { renderWithProviders } from '../../../../test/renderWithProviders';
import { PaymentsTab } from './PaymentsTab';

const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof customerPaymentService.list>(),
  record: vi.fn<typeof customerPaymentService.record>(),
  decide: vi.fn<typeof customerPaymentService.decide>(),
  allocate: vi.fn<typeof customerPaymentService.allocate>(),
  invoices: vi.fn<typeof hireInvoiceService.list>(),
  customers: vi.fn<typeof customerService.list>(),
  getCustomer: vi.fn<typeof customerService.get>(),
}));
vi.mock('../../../../api/services/financeService', () => ({
  customerPaymentService: {
    list: mocks.list,
    record: mocks.record,
    decide: mocks.decide,
    allocate: mocks.allocate,
  },
  hireInvoiceService: { list: mocks.invoices },
}));
vi.mock('../../../../api/services/customerService', () => ({
  customerService: { list: mocks.customers, get: mocks.getCustomer },
}));
vi.mock('../../../../api/services/staffService', () => ({
  staffService: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 }),
  },
}));

const VERIFY = [P.tenantFinanceRead, P.tenantFinanceVerify, P.tenantFinancePayment];

beforeEach(() => {
  mocks.list.mockResolvedValue(page([makePayment()]));
  mocks.customers.mockResolvedValue(page([CUSTOMER]));
  mocks.getCustomer.mockResolvedValue(CUSTOMER);
  mocks.invoices.mockResolvedValue(page([makeInvoice()]));
});

const MENU = 'Actions for payment TRX-1';

describe('PaymentsTab', () => {
  it('shows claimed payments by default, separately from verified ones', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PaymentsTab timeZone="UTC" />, { tenantPermissions: VERIFY });
    expect(await screen.findByText(/do NOT reduce customer balances/)).toBeInTheDocument();
    expect(mocks.list.mock.lastCall?.[0].filters?.status).toBe('CLAIMED');
    await user.click(screen.getByRole('button', { name: 'Verified' }));
    await waitFor(() => {
      expect(mocks.list.mock.lastCall?.[0].filters?.status).toBe('VERIFIED');
    });
  });

  it('does not let the recorder verify their own payment (segregation of duties)', async () => {
    const user = userEvent.setup();
    mocks.list.mockResolvedValue(page([makePayment({ recorded_by: ME })]));
    renderWithProviders(<PaymentsTab timeZone="UTC" />, { tenantPermissions: VERIFY });
    await user.click(await screen.findByRole('button', { name: MENU }));
    const item = screen.getByRole('menuitem', { name: /not allowed: you recorded it/ });
    expect(item).toHaveAttribute('aria-disabled', 'true');
    await user.keyboard('{Escape}');
    await user.click(screen.getByText('TRX-1'));
    expect(await screen.findByText(/someone else must verify or reject it/)).toBeInTheDocument();
  });

  it('requires a reason to reject and shows SEGREGATION_OF_DUTIES from the server', async () => {
    const user = userEvent.setup();
    mocks.decide
      .mockRejectedValueOnce(
        new ApiError({
          status: 422,
          code: 'SEGREGATION_OF_DUTIES',
          message: 'The person who recorded a payment cannot verify it',
          correlationId: 'c',
        }),
      )
      .mockResolvedValue(makePayment({ status: 'REJECTED' }));
    renderWithProviders(<PaymentsTab timeZone="UTC" />, { tenantPermissions: VERIFY });
    await user.click(await screen.findByRole('button', { name: MENU }));
    await user.click(screen.getByRole('menuitem', { name: 'Verify / reject' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Decision/ }));
    await user.click(await screen.findByRole('option', { name: 'Reject (not received)' }));
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }));
    expect(await within(dialog).findByText('A reason is required to reject')).toBeInTheDocument();
    expect(mocks.decide).not.toHaveBeenCalled();
    await user.type(within(dialog).getByRole('textbox', { name: /Note/ }), 'Not on statement');
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }));
    expect(await within(dialog).findByText(/^SEGREGATION_OF_DUTIES: /)).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }));
    await waitFor(() => {
      expect(mocks.decide).toHaveBeenLastCalledWith(
        makePayment().id,
        { verified: false, note: 'Not on statement' },
        expect.any(String),
      );
    });
  });

  it('hides verify and record actions while READ_ONLY', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PaymentsTab timeZone="UTC" />, {
      tenantPermissions: VERIFY,
      accessState: 'READ_ONLY',
    });
    await user.click(await screen.findByRole('button', { name: MENU }));
    expect(screen.queryByRole('menuitem', { name: /Verify/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Record payment' })).not.toBeInTheDocument();
  });

  it('records a bank payment: reference required, allocations limited to the amount', async () => {
    const user = userEvent.setup();
    mocks.record.mockResolvedValue(makePayment());
    renderWithProviders(<PaymentsTab timeZone="UTC" />, { tenantPermissions: VERIFY });
    await user.click(await screen.findByRole('button', { name: 'Record payment' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Customer/ }));
    await user.click(await screen.findByRole('option', { name: 'ACME · Acme Builders' }));
    await user.type(within(dialog).getByRole('textbox', { name: /^Amount/ }), '100000');
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    expect(
      await within(dialog).findByText('A reference is required for bank and mobile money payments'),
    ).toBeInTheDocument();
    await user.type(
      within(dialog).getByRole('textbox', { name: /Transaction reference/ }),
      'TRX-9',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    await user.click(await within(dialog).findByRole('button', { name: 'Next' }));
    await user.click(await within(dialog).findByRole('button', { name: 'Allocate to an invoice' }));
    await user.click(within(dialog).getByRole('combobox', { name: 'Invoice 1' }));
    await user.type(within(dialog).getByRole('combobox', { name: 'Invoice 1' }), '0001');
    await waitFor(() => {
      expect(mocks.invoices).toHaveBeenCalledWith(
        expect.objectContaining({
          q: '0001',
          filters: { status: 'ISSUED', customer_id: CUSTOMER.id },
        }),
        expect.any(AbortSignal),
      );
    });
    await user.click(await screen.findByRole('option', { name: /HINV-2026-00001/ }));
    await user.type(within(dialog).getByRole('textbox', { name: /^Amount/ }), '150000');
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    expect(
      await within(dialog).findByText('Allocations exceed the payment amount'),
    ).toBeInTheDocument();
    const alloc = within(dialog).getByRole('textbox', { name: /^Amount/ });
    await user.clear(alloc);
    await user.type(alloc, '60000');
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    await user.click(await within(dialog).findByRole('button', { name: 'Record payment' }));
    await waitFor(() => {
      expect(mocks.record).toHaveBeenCalledTimes(1);
    });
    expect(mocks.record.mock.calls[0]?.[0]).toMatchObject({
      customer_id: CUSTOMER.id,
      method: 'BANK',
      amount: '100000',
      currency: 'TZS',
      reference: 'TRX-9',
      allocations: [{ invoice_id: makeInvoice().id, amount: '60000' }],
    });
  });
});
