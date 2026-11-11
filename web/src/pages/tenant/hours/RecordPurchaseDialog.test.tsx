import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { HoursPurchaseDto, HoursQuoteDto } from '../../../api/hoursTypes';
import type { hoursService } from '../../../api/services/hoursService';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { renderWithProviders } from '../../../test/renderWithProviders';
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

function open(perms: string[], fieldNoncashPayments = false) {
  renderWithProviders(
    <RecordPurchaseDialog
      timeZone="Africa/Dar_es_Salaam"
      field
      walkInAllowed={false}
      fieldNoncashPayments={fieldNoncashPayments}
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

    // The first line defaults to the whole balance.
    await user.click(screen.getByRole('button', { name: 'Add payment' }));
    const amounts = () => screen.getAllByRole('textbox', { name: /^Amount/ });
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
    await user.click(screen.getByRole('button', { name: 'Add payment' }));
    expect(await methodOptions(user, 0)).toEqual(['Cash']);
  });

  it('offers bank and mobile money to field staff when field_noncash_payments is on', async () => {
    const user = userEvent.setup();
    open([RECORD], true);
    await toPaymentStep(user);
    expect(screen.queryByText(/recorded by the office/)).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Add payment' }));
    expect(await methodOptions(user, 0)).toEqual(['Cash', 'Bank transfer', 'Mobile money']);
  });

  it('records not paid yet with no lines', async () => {
    const user = userEvent.setup();
    open([RECORD]);
    await toPaymentStep(user);
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findAllByText('Not paid yet')).not.toHaveLength(0);
    await user.click(screen.getByRole('button', { name: 'Record purchase' }));
    await waitFor(() => {
      expect(mocks.record).toHaveBeenCalled();
    });
    expect(nthCall().payments).toEqual([]);
  });
});
