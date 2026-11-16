import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../../api/ApiError';
import type { CreditInvoiceDto } from '../../../../api/hoursTypes';
import type { creditInvoiceService } from '../../../../api/services/creditInvoiceService';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { HOURS_ROUTES } from '../../../../navigation/hoursRoutes';
import { renderWithProviders } from '../../../../test/renderWithProviders';
import { HoursBalancesPage } from '../HoursBalancesPage';
import { CreditInvoiceDetailPage } from './CreditInvoiceDetailPage';
import { CreditInvoicesPage } from './CreditInvoicesPage';
import { groupedAmount } from './creditInvoiceDisplay';
import { invoicePaymentSchema, toInvoicePaymentPayload } from './invoicePaymentForm';

const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof creditInvoiceService.list>(),
  get: vi.fn<typeof creditInvoiceService.get>(),
  recordPayment: vi.fn<typeof creditInvoiceService.recordPayment>(),
  customerHours: vi.fn<typeof creditInvoiceService.customerHours>(),
}));
vi.mock('../../../../api/services/creditInvoiceService', () => ({
  creditInvoiceService: mocks,
}));
vi.mock('../../../../api/services/hoursService', () => ({
  hoursService: { uploadEvidence: vi.fn() },
}));
vi.mock('../../../../components/forms/FormikDateTimeField', () => ({
  FormikDateTimeField: ({ name, label }: { name: string; label: string }) => (
    <FormikTextField name={name} label={label} />
  ),
}));
vi.mock('../../shared/financePickers', () => ({
  FormikStaffIdPicker: ({ name, label }: { name: string; label: string }) => (
    <FormikTextField name={name} label={label} />
  ),
  CustomerFilter: () => null,
  MachineFilter: () => null,
}));

const READ = 'tenant.hours.read';
const PAY = 'tenant.hours.invoice_payment';
const OFFICE = 'tenant.finance.payment';

const INVOICE: CreditInvoiceDto = {
  id: 'i1',
  invoice_number: 'CI-2026-00001',
  purchase_id: 'p1',
  purchase_number: 'HP-2026-00007',
  customer_id: 'c1',
  customer_name: 'Mwanza Builders',
  machine_id: 'm1',
  machine_code: 'EX-01',
  machine_name: 'Excavator',
  currency: 'TZS',
  hours: '4',
  unit_price: '85000',
  amount: '340000',
  paid: '170000',
  paid_verified: '0',
  balance: '170000',
  payment_terms_days: 30,
  issued_at: '2026-11-01T08:00:00Z',
  due_date: '2026-12-01',
  status: 'PART_PAID',
  overdue: false,
  days_overdue: 0,
  created_by: 'u1',
  created_by_name: 'Asha',
  payments: [
    {
      id: 'x1',
      payment_id: 'pay1',
      amount: '170000',
      method: 'MOBILE_MONEY',
      reference: 'QK12AB34',
      collection_number: null,
      payment_status: 'CLAIMED',
      received_at: '2026-11-02T08:00:00Z',
      received_by_staff_id: null,
      received_by_staff_name: 'Juma',
      recorded_by: 'u2',
      recorded_by_name: 'Juma',
      created_at: '2026-11-02T08:00:00Z',
      counts: true,
    },
  ],
};

const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 25 });

function openDetail(perms: string[]) {
  renderWithProviders(
    <Routes>
      <Route path={HOURS_ROUTES.creditInvoiceDetail} element={<CreditInvoiceDetailPage />} />
    </Routes>,
    { route: '/tenant/hours/credit-invoices/i1', tenantPermissions: perms },
  );
}

beforeEach(() => {
  mocks.list.mockReset().mockResolvedValue(page([{ ...INVOICE, overdue: true, days_overdue: 3 }]));
  mocks.get.mockReset().mockResolvedValue(INVOICE);
  mocks.recordPayment.mockReset().mockResolvedValue({ ...INVOICE, status: 'PAID', balance: '0' });
  mocks.customerHours.mockReset().mockResolvedValue([
    {
      customer_id: 'c1',
      customer_name: 'Mwanza Builders',
      bought: '20',
      activated: '16',
      used: '9.5',
      left: '6.5',
      awaiting_activation: '4',
      credit_owed: '170000',
    },
  ]);
});

describe('Credit invoices list', () => {
  it('shows status, due date, overdue and the balance', async () => {
    renderWithProviders(<CreditInvoicesPage />, { tenantPermissions: [READ] });
    const row = (await screen.findByText('CI-2026-00001')).closest('tr') as HTMLElement;
    expect(within(row).getByText('Mwanza Builders')).toBeInTheDocument();
    expect(within(row).getByText('Part paid')).toBeInTheDocument();
    expect(within(row).getByText('Overdue 3 d')).toBeInTheDocument();
    expect(within(row).getByText('2026-12-01')).toBeInTheDocument();
    expect(mocks.list.mock.calls[0]?.[0].sort).toBe('due_date');
  });
});

describe('Credit invoice detail', () => {
  it('lists the payments and offers Record payment to holders of invoice_payment', async () => {
    openDetail([READ, PAY]);
    expect(await screen.findByText('QK12AB34')).toBeInTheDocument();
    expect(screen.getByText('Claimed (waiting for verification)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Record payment' })).toBeInTheDocument();
  });

  it('hides Record payment without the permission or when nothing is left to pay', async () => {
    openDetail([READ]);
    await screen.findByText('QK12AB34');
    expect(screen.queryByRole('button', { name: 'Record payment' })).not.toBeInTheDocument();
  });

  it('hides Record payment on a paid invoice', async () => {
    mocks.get.mockResolvedValue({ ...INVOICE, status: 'PAID', balance: '0' });
    openDetail([READ, PAY]);
    await screen.findByText('QK12AB34');
    expect(screen.queryByRole('button', { name: 'Record payment' })).not.toBeInTheDocument();
  });

  it('records the full balance in cash by default (field staff: cash only)', async () => {
    const user = userEvent.setup();
    openDetail([READ, PAY]);
    await user.click(await screen.findByRole('button', { name: 'Record payment' }));
    expect(screen.getByRole('textbox', { name: /Amount received/ })).toHaveValue('170000');
    expect(screen.getByText('Pays the invoice in full.')).toBeInTheDocument();
    expect(
      screen.getByText('Bank and mobile-money payments are recorded by the office.'),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: /Method/ }));
    expect(
      within(screen.getByRole('listbox'))
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['Cash']);
    await user.keyboard('{Escape}');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Full payment')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Record payment' }));
    await waitFor(() => {
      expect(mocks.recordPayment).toHaveBeenCalled();
    });
    const [id, body] = mocks.recordPayment.mock.calls[0] ?? [];
    expect(id).toBe('i1');
    expect(body).toMatchObject({ amount: '170000', method: 'CASH', staff_member_id: null });
  });

  it('takes a part payment by bank from the office, with its reference', async () => {
    const user = userEvent.setup();
    openDetail([READ, PAY, OFFICE]);
    await user.click(await screen.findByRole('button', { name: 'Record payment' }));
    const amount = screen.getByRole('textbox', { name: /Amount received/ });
    await user.clear(amount);
    await user.type(amount, '200000');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(
      await screen.findByText('The amount is more than the balance of the invoice.'),
    ).toBeInTheDocument();
    await user.clear(amount);
    await user.type(amount, '50000');
    expect(screen.getByText('A part payment; the rest stays owed.')).toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: /Method/ }));
    await user.click(screen.getByRole('option', { name: 'Bank transfer' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(
      await screen.findByText('Reference is required for bank and mobile money'),
    ).toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: /Reference/ }), 'TT-9');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Part payment')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Record payment' }));
    await waitFor(() => {
      expect(mocks.recordPayment).toHaveBeenCalled();
    });
    expect(mocks.recordPayment.mock.calls[0]?.[1]).toMatchObject({
      amount: '50000',
      method: 'BANK',
      reference: 'TT-9',
    });
  });

  it('explains a refused payment in plain words', async () => {
    mocks.recordPayment.mockRejectedValue(
      new ApiError({ status: 422, code: 'INVOICE_OVERPAYMENT', message: 'x', correlationId: null }),
    );
    const user = userEvent.setup();
    openDetail([READ, PAY]);
    await user.click(await screen.findByRole('button', { name: 'Record payment' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Record payment' }));
    expect(await screen.findByText(/more than what is left to pay/)).toBeInTheDocument();
  });
});

describe('Customer hours balances', () => {
  it('lists every customer’s bought, used, left and credit owed', async () => {
    renderWithProviders(<HoursBalancesPage />, { tenantPermissions: [READ] });
    const row = (await screen.findByText('Mwanza Builders')).closest('tr') as HTMLElement;
    expect(within(row).getByText('6.5 h')).toBeInTheDocument();
    expect(within(row).getByRole('link', { name: '170,000' })).toHaveAttribute(
      'href',
      '/tenant/hours/credit-invoices?customer_id=c1',
    );
  });
});

describe('invoice payment form', () => {
  it('needs no reference for cash and sends no custodian for bank', () => {
    const v = {
      amount: '100',
      method: 'BANK' as const,
      reference: ' R1 ',
      received_at: '2026-11-16T08:00:00Z',
      staff_member_id: 's1',
      note: '',
      evidence: null,
      balance: '100',
    };
    expect(invoicePaymentSchema.isValidSync(v)).toBe(true);
    expect(invoicePaymentSchema.isValidSync({ ...v, reference: '' })).toBe(false);
    expect(invoicePaymentSchema.isValidSync({ ...v, method: 'CASH', reference: '' })).toBe(true);
    expect(toInvoicePaymentPayload(v, 'k', { office: true })).toMatchObject({
      reference: 'R1',
      staff_member_id: null,
    });
    expect(groupedAmount('1234500.50')).toBe('1,234,500.5');
  });
});
