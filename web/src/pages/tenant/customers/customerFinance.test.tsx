import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { receivablesService } from '../../../api/services/financeService';
import type { CustomerBalanceDto, CustomerStatementDto } from '../../../api/types';
import { CUSTOMER_ID, makePayment } from '../../../test/financeFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { CustomerBalanceTab, CustomerStatementTab } from './CustomerFinanceTabs';

const mocks = vi.hoisted(() => ({
  balances: vi.fn<typeof receivablesService.balances>(),
  statement: vi.fn<typeof receivablesService.statement>(),
}));
vi.mock('../../../api/services/financeService', () => ({ receivablesService: mocks }));

const balance = (currency: string, o: Partial<CustomerBalanceDto> = {}): CustomerBalanceDto => ({
  customer_id: CUSTOMER_ID,
  currency,
  invoiced: '1416000.0000',
  reversed: '0.0000',
  verified_payments: '400000.0000',
  balance: '1016000.0000',
  unallocated_credit: '0.0000',
  claimed_unverified: '500000.0000',
  open_invoices: 1,
  ...o,
});

const statement = (currency: string): CustomerStatementDto => ({
  customer_id: CUSTOMER_ID,
  currency,
  period_from: '2026-10-01',
  period_to: '2026-10-21',
  opening_balance: '0.0000',
  lines: [
    {
      at: '2026-10-21T08:00:00Z',
      kind: 'INVOICE',
      reference: 'HINV-2026-00001',
      description: 'Hire invoice',
      debit: '1416000.0000',
      credit: '0.0000',
      running_balance: '1416000.0000',
    },
  ],
  total_debits: '1416000.0000',
  total_credits: '0.0000',
  closing_balance: '1416000.0000',
  claimed_unverified: [makePayment({ currency })],
  claimed_unverified_total: '500000.0000',
});

beforeEach(() => {
  mocks.balances.mockResolvedValue([
    balance('TZS'),
    balance('USD', { invoiced: '100.0000', balance: '100.0000', claimed_unverified: '0.0000' }),
  ]);
  mocks.statement.mockImplementation((_id, q) => Promise.resolve(statement(q.currency ?? 'TZS')));
});

const PERMS = [P.tenantCustomerRead, P.tenantFinanceRead];

describe('Customer balance and statement', () => {
  it('shows one balance per currency with claimed money separate', async () => {
    renderWithProviders(<CustomerBalanceTab customerId={CUSTOMER_ID} />, {
      tenantPermissions: PERMS,
    });
    const tzs = await screen.findByRole('region', { name: 'Balance in TZS' });
    expect(within(tzs).getByText('TZS 1,016,000.00')).toBeInTheDocument();
    expect(within(tzs).getByText(/Claimed, not yet verified/)).toHaveTextContent('TZS 500,000.00');
    const usd = screen.getByRole('region', { name: 'Balance in USD' });
    expect(within(usd).getAllByText('USD 100.00').length).toBeGreaterThan(0);
    expect(within(usd).queryByText(/TZS/)).not.toBeInTheDocument();
  });

  it('loads the statement per currency with opening / closing and unverified claims', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CustomerStatementTab customerId={CUSTOMER_ID} timeZone="UTC" />, {
      tenantPermissions: PERMS,
    });
    const summary = await screen.findByRole('table', { name: 'Statement summary' });
    expect(within(summary).getByText('Opening balance')).toBeInTheDocument();
    expect(within(summary).getByText('Closing balance')).toBeInTheDocument();
    expect(mocks.statement).toHaveBeenLastCalledWith(
      CUSTOMER_ID,
      expect.objectContaining({ currency: 'TZS' }),
      expect.any(AbortSignal),
    );
    expect(screen.getByRole('table', { name: 'Claimed unverified payments' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'USD' }));
    await waitFor(() => {
      expect(mocks.statement).toHaveBeenLastCalledWith(
        CUSTOMER_ID,
        expect.objectContaining({ currency: 'USD' }),
        expect.any(AbortSignal),
      );
    });
    expect(await screen.findByText(/USD statement/)).toBeInTheDocument();
  });
});
