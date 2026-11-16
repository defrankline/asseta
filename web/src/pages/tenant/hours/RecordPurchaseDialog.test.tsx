import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { HoursPurchaseDto, HoursQuoteDto } from '../../../api/hoursTypes';
import type { hoursService } from '../../../api/services/hoursService';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { purchaseRecordedText } from './purchaseForm';
import { RecordPurchaseDialog } from './RecordPurchaseDialog';

const mocks = vi.hoisted(() => ({
  quote: vi.fn<typeof hoursService.quotePurchase>(),
  record: vi.fn<typeof hoursService.recordPurchase>(),
}));
vi.mock('../../../api/services/hoursService', () => ({
  hoursService: {
    quotePurchase: mocks.quote,
    recordPurchase: mocks.record,
    uploadEvidence: vi.fn(),
  },
}));
// Plain inputs stand in for the async pickers (their own tests cover them).
vi.mock('../shared/financePickers', () => {
  const Plain = ({ name, label }: { name: string; label: string }) => (
    <FormikTextField name={name} label={label} />
  );
  return {
    FormikCustomerIdPicker: Plain,
    FormikMachineIdPicker: Plain,
    FormikStaffIdPicker: Plain,
  };
});
vi.mock('../shared/lookupPickers', () => ({ FormikJobSitePicker: () => null }));

const QUOTE: HoursQuoteDto = {
  machine_id: 'm1',
  customer_id: 'c1',
  hours: '6',
  hourly_rate: '95000.0000',
  discount_percent: '0',
  effective_rate: '95000.0000',
  amount: '570000.0000',
  currency: 'TZS',
  minimum_hours: '1',
};

const RECORD = 'tenant.collection.record';
const FINANCE = 'tenant.finance.payment';

function open(
  perms: string[],
  fieldNoncashPayments = false,
  extra: { fieldCreditSales?: boolean; creditAllowed?: boolean | null; walkIn?: boolean } = {},
) {
  renderWithProviders(
    <RecordPurchaseDialog
      timeZone="Africa/Dar_es_Salaam"
      field
      walkInAllowed={extra.walkIn ?? false}
      fieldNoncashPayments={fieldNoncashPayments}
      fieldCreditSales={extra.fieldCreditSales ?? false}
      creditAllowed={extra.creditAllowed ?? null}
      onClose={vi.fn()}
      onRecorded={vi.fn()}
    />,
    { tenantPermissions: ['tenant.hours.purchase', ...perms] },
  );
}

async function toPaymentStep(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Customer'), 'c1');
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await user.type(screen.getByLabelText('Machine'), 'm1');
  await user.type(screen.getByLabelText(/Hours bought/), '6');
  expect(await screen.findByText('Total: TZS 570,000 (6 h × 95,000/h)')).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByRole('button', { name: 'Add payment' });
}

const amounts = () => screen.getAllByRole('textbox', { name: /^Amount/ });

async function methodOptions(user: ReturnType<typeof userEvent.setup>, index: number) {
  await user.click(screen.getAllByRole('combobox', { name: /Method/ }).at(index) as HTMLElement);
  const names = within(screen.getByRole('listbox'))
    .getAllByRole('option')
    .map((o) => o.textContent);
  await user.keyboard('{Escape}');
  return names;
}

function nthCall() {
  const call = mocks.record.mock.calls[0];
  if (call === undefined) throw new Error('recordPurchase was not called');
  return call[0];
}

beforeEach(() => {
  mocks.quote.mockReset().mockResolvedValue(QUOTE);
  mocks.record.mockReset().mockResolvedValue({ id: 'p1' } as HoursPurchaseDto);
});

describe('RecordPurchaseDialog payments', () => {
  it('splits the sale across lines, shows paid and balance, and sends payments', async () => {
    const user = userEvent.setup();
    open([RECORD, FINANCE]);
    await toPaymentStep(user);
    expect(screen.queryByText(/recorded by the office/)).not.toBeInTheDocument();

    // The form opens with one Cash line at the whole total.
    expect(amounts()).toHaveLength(1);
    expect(amounts()[0]).toHaveValue('570000');
    expect(screen.getByText('Paid TZS 570,000 of TZS 570,000 · Balance TZS 0')).toBeInTheDocument();
    expect(screen.getByText('Fully paid')).toBeInTheDocument();

    await user.clear(amounts().at(0) as HTMLElement);
    await user.type(amounts().at(0) as HTMLElement, '300000');
    expect(screen.getByText('Part paid (balance TZS 270,000)')).toBeInTheDocument();

    // A second line takes the rest by bank, with its reference.
    await user.click(screen.getByRole('button', { name: 'Add payment' }));
    expect(amounts()[1]).toHaveValue('270000');
    expect(amounts()[0]).toHaveValue('300000');
    expect(await methodOptions(user, 1)).toEqual(['Cash', 'Bank transfer', 'Mobile money']);
    await user.click(screen.getAllByRole('combobox', { name: /Method/ }).at(1) as HTMLElement);
    await user.click(screen.getByRole('option', { name: 'Bank transfer' }));
    await user.type(screen.getByRole('textbox', { name: /Reference/ }), 'TT-1');

    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText(/Bank transfer · TZS 270,000 · ref TT-1/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Record purchase' }));
    await waitFor(() => {
      expect(mocks.record).toHaveBeenCalled();
    });
    const body = nthCall();
    expect(body.payment).toBeUndefined();
    expect(body.payments?.map((p) => [p.method, p.amount, p.reference])).toEqual([
      ['CASH', '300000', null],
      ['BANK', '270000', 'TT-1'],
    ]);
  });

  it('blocks payments over the total and lets a line be removed', async () => {
    const user = userEvent.setup();
    open([RECORD]);
    await toPaymentStep(user);
    await user.click(screen.getByRole('button', { name: 'Add payment' }));
    const second = screen.getAllByRole('textbox', { name: /^Amount/ }).at(1) as HTMLElement;
    expect(second).toHaveValue('');
    await user.type(second, '1000');
    expect(
      screen.getByText('The payments add up to more than the total. Lower an amount.'),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.queryByRole('button', { name: 'Record purchase' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Remove payment 2' }));
    expect(screen.getByText('Fully paid')).toBeInTheDocument();
  });

  it('offers only cash to field staff unless the company allows non-cash', async () => {
    const user = userEvent.setup();
    open([RECORD]);
    await toPaymentStep(user);
    expect(
      screen.getByText('Bank and mobile-money payments are recorded by the office.'),
    ).toBeInTheDocument();
    expect(await methodOptions(user, 0)).toEqual(['Cash']);
  });

  it('offers bank and mobile money to field staff when field_noncash_payments is on', async () => {
    const user = userEvent.setup();
    open([RECORD], true);
    await toPaymentStep(user);
    expect(screen.queryByText(/recorded by the office/)).not.toBeInTheDocument();
    expect(await methodOptions(user, 0)).toEqual(['Cash', 'Bank transfer', 'Mobile money']);
  });

  it('opens with a Cash line that follows the total until the amount is typed', async () => {
    mocks.quote.mockImplementation(({ hours }) =>
      Promise.resolve({ ...QUOTE, hours, amount: `${Number(hours) * 95000}.0000` }),
    );
    const user = userEvent.setup();
    open([RECORD]);
    await toPaymentStep(user);
    expect(amounts()[0]).toHaveValue('570000');
    expect(screen.getByText('Fully paid')).toBeInTheDocument();

    // Hours change the total: the untouched line follows it.
    await user.click(screen.getByRole('button', { name: 'Back' }));
    await user.clear(screen.getByLabelText(/Hours bought/));
    await user.type(screen.getByLabelText(/Hours bought/), '4');
    expect(await screen.findByText('Total: TZS 380,000 (4 h × 95,000/h)')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await screen.findByRole('button', { name: 'Add payment' });
    expect(amounts()[0]).toHaveValue('380000');

    // Typed: never changed again.
    await user.clear(amounts().at(0) as HTMLElement);
    await user.type(amounts().at(0) as HTMLElement, '100000');
    await user.click(screen.getByRole('button', { name: 'Back' }));
    await user.clear(screen.getByLabelText(/Hours bought/));
    await user.type(screen.getByLabelText(/Hours bought/), '6');
    expect(await screen.findByText('Total: TZS 570,000 (6 h × 95,000/h)')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await screen.findByRole('button', { name: 'Add payment' });
    expect(amounts()[0]).toHaveValue('100000');
    expect(screen.getByText('Part paid (balance TZS 470,000)')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Record purchase' }));
    await waitFor(() => {
      expect(mocks.record).toHaveBeenCalled();
    });
    expect(nthCall().payments?.map((p) => [p.method, p.amount])).toEqual([['CASH', '100000']]);
  });

  it('records not paid yet when the opening line is removed', async () => {
    const user = userEvent.setup();
    open([RECORD]);
    await toPaymentStep(user);
    await user.click(screen.getByRole('button', { name: 'Remove payment 1' }));
    expect(screen.queryAllByRole('textbox', { name: /^Amount/ })).toHaveLength(0);
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findAllByText('Not paid yet')).not.toHaveLength(0);
    await user.click(screen.getByRole('button', { name: 'Record purchase' }));
    await waitFor(() => {
      expect(mocks.record).toHaveBeenCalled();
    });
    expect(nthCall().payments).toEqual([]);
  });
});

const ACTIVATE = 'tenant.hours.credit_activate';

describe('RecordPurchaseDialog credit line', () => {
  it('is not offered to field staff while field credit sales are off', async () => {
    const user = userEvent.setup();
    open([RECORD]);
    await toPaymentStep(user);
    expect(await methodOptions(user, 0)).toEqual(['Cash']);
  });

  it('is offered when the company allows field credit sales', async () => {
    const user = userEvent.setup();
    open([RECORD], false, { fieldCreditSales: true });
    await toPaymentStep(user);
    expect(await methodOptions(user, 0)).toEqual(['Cash', 'Credit']);
  });

  it('is never offered when the company switched credit off', async () => {
    const user = userEvent.setup();
    open([RECORD, ACTIVATE], false, { fieldCreditSales: true, creditAllowed: false });
    await toPaymentStep(user);
    expect(await methodOptions(user, 0)).toEqual(['Cash']);
  });

  it('takes an amount only, at most one line, and sends CREDIT without money fields', async () => {
    const user = userEvent.setup();
    open([RECORD, FINANCE, ACTIVATE]);
    await toPaymentStep(user);
    await user.clear(amounts().at(0) as HTMLElement);
    await user.type(amounts().at(0) as HTMLElement, '400000');
    await user.click(screen.getByRole('button', { name: 'Add payment' }));
    expect(await methodOptions(user, 1)).toEqual([
      'Cash',
      'Bank transfer',
      'Mobile money',
      'Credit',
    ]);
    const timeFields = screen.getAllByLabelText(/Received at/).length;
    await user.click(screen.getAllByRole('combobox', { name: /Method/ }).at(1) as HTMLElement);
    await user.click(screen.getByRole('option', { name: 'Credit' }));
    // Amount only: no reference, time or evidence on the credit line.
    expect(screen.getAllByLabelText(/Received at/).length).toBe(timeFields / 2);
    expect(screen.getByText(/A credit invoice is created when you save/)).toBeInTheDocument();
    // One credit line: the first line no longer offers Credit.
    expect(await methodOptions(user, 0)).toEqual(['Cash', 'Bank transfer', 'Mobile money']);

    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(
      await screen.findByText(/Credit · TZS 170,000 · paid later on a credit invoice/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/The credit part creates an invoice automatically/),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Record purchase' }));
    await waitFor(() => {
      expect(mocks.record).toHaveBeenCalled();
    });
    const body = nthCall();
    expect(body.payments?.[1]).toEqual({
      method: 'CREDIT',
      amount: '170000',
      evidence_attachment_ids: [],
    });
    expect(body).not.toHaveProperty('job');
  });

  it('keeps credit for registered customers (walk-ins pay now)', async () => {
    const user = userEvent.setup();
    open([RECORD, ACTIVATE], false, { walkIn: true });
    await user.click(screen.getByLabelText('New walk-in customer'));
    await user.type(screen.getByLabelText(/Walk-in customer name/), 'Asha');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.type(screen.getByLabelText('Machine'), 'm1');
    await user.type(screen.getByLabelText(/Hours bought/), '6');
    await screen.findByText('Total: TZS 570,000 (6 h × 95,000/h)');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await screen.findByRole('button', { name: 'Add payment' });
    expect(await methodOptions(user, 0)).toEqual(['Cash']);
  });

  it('explains a refused credit sale in plain words', async () => {
    mocks.record.mockRejectedValue(
      new ApiError({
        status: 403,
        code: 'CREDIT_SALES_NOT_ALLOWED',
        message: 'x',
        correlationId: null,
      }),
    );
    const user = userEvent.setup();
    open([RECORD], false, { fieldCreditSales: true });
    await toPaymentStep(user);
    await user.click(screen.getAllByRole('combobox', { name: /Method/ }).at(0) as HTMLElement);
    await user.click(screen.getByRole('option', { name: 'Credit' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Record purchase' }));
    expect(await screen.findByText(/does not let field staff sell on credit/)).toBeInTheDocument();
  });

  it('names the credit invoice in the success message', () => {
    expect(purchaseRecordedText({ purchase_number: 'HP-1', credit_invoice: null })).toBe(
      'Hours purchase HP-1 recorded.',
    );
    expect(
      purchaseRecordedText({
        purchase_number: 'HP-1',
        credit_invoice: {
          id: 'i1',
          invoice_number: 'CI-2026-00001',
          amount: '170000',
          paid: '0',
          balance: '170000',
          due_date: '2026-12-16',
          status: 'UNPAID',
          overdue: false,
        },
      }),
    ).toBe(
      'Hours purchase HP-1 recorded. Credit invoice CI-2026-00001 created for 170000, due 2026-12-16.',
    );
  });
});
