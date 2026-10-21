import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../../access/permissionCodes';
import type { cashService } from '../../../../api/services/cashService';
import type { staffService } from '../../../../api/services/staffService';
import {
  makeDay,
  makeHandover,
  ME,
  page,
  STAFF_ID,
  SUPERVISOR,
} from '../../../../test/financeFixtures';
import { renderWithProviders } from '../../../../test/renderWithProviders';
import { CustodyTab } from './CustodyTab';
import { HandoversTab } from './HandoversTab';
import { RECONCILIATION_FORMULA, ReconciliationTab } from './ReconciliationTab';

const mocks = vi.hoisted(() => ({
  custody: vi.fn<typeof cashService.custody>(),
  reconciliation: vi.fn<typeof cashService.reconciliation>(),
  listHandovers: vi.fn<typeof cashService.listHandovers>(),
  decideHandover: vi.fn<typeof cashService.decideHandover>(),
  issueFloat: vi.fn<typeof cashService.issueFloat>(),
  staff: vi.fn<typeof staffService.list>(),
}));
vi.mock('../../../../api/services/cashService', () => ({ cashService: mocks }));
vi.mock('../../../../api/services/staffService', () => ({
  staffService: { list: mocks.staff, get: vi.fn().mockResolvedValue(SUPERVISOR) },
}));

const READ = [P.tenantFinanceRead, P.tenantStaffRead];

beforeEach(() => {
  mocks.staff.mockResolvedValue(page([SUPERVISOR]));
  mocks.listHandovers.mockResolvedValue(page([makeHandover()]));
});

describe('ReconciliationTab (§10 #8)', () => {
  it('shows the server figures of the formula and claims separately, never recomputed', async () => {
    // Deliberately "inconsistent" outstanding values prove the UI shows API numbers verbatim.
    mocks.reconciliation.mockResolvedValue({
      staff_member_id: STAFF_ID,
      currency: 'TZS',
      timezone: 'Africa/Dar_es_Salaam',
      days: [makeDay({ day: '2026-10-20' }), makeDay({ outstanding: '200000.0000' })],
    });
    renderWithProviders(
      <ReconciliationTab supervisor={SUPERVISOR} onSupervisorChange={vi.fn()} />,
      {
        tenantPermissions: READ,
      },
    );
    expect(screen.getByText(`${RECONCILIATION_FORMULA}.`)).toBeInTheDocument();
    const card = await screen.findByRole('region', { name: 'Reconciliation 2026-10-21' });
    const calc = within(card).getByRole('table', { name: 'Outstanding calculation' });
    for (const [label, value] of [
      ['Opening cash', 'TZS 100,000.00'],
      ['Floats issued', 'TZS 50,000.00'],
      ['Cash collections', 'TZS 200,000.00'],
      ['Approved cash expenses', 'TZS 30,000.00'],
      ['Verified handovers', 'TZS 120,000.00'],
    ] as const) {
      const row = within(calc).getByText(label).closest('tr');
      expect(row).not.toBeNull();
      expect(within(row as HTMLElement).getByText(value)).toBeInTheDocument();
    }
    expect(within(card).getByTestId('outstanding')).toHaveTextContent('TZS 200,000.00');
    const claims = within(card).getByRole('table', { name: 'Not yet verified' });
    expect(within(claims).getByText('TZS 90,000.00')).toBeInTheDocument();
    expect(within(claims).getByText('TZS 15,000.00')).toBeInTheDocument();
    expect(within(claims).getByText('TZS 40,000.00')).toBeInTheDocument();
    expect(within(card).getByTestId('outstanding-if-verified')).toHaveTextContent('TZS 110,000.00');
    expect(screen.getByRole('table', { name: 'Daily reconciliation' })).toBeInTheDocument();
    expect(mocks.reconciliation).toHaveBeenCalledWith(
      expect.objectContaining({ staffMemberId: STAFF_ID, currency: undefined }),
      expect.any(AbortSignal),
    );
  });

  it('asks for a supervisor before loading', () => {
    renderWithProviders(<ReconciliationTab supervisor={null} onSupervisorChange={vi.fn()} />, {
      tenantPermissions: READ,
    });
    expect(screen.getByText('Choose a supervisor')).toBeInTheDocument();
    expect(mocks.reconciliation).not.toHaveBeenCalled();
  });
});

describe('CustodyTab', () => {
  it('shows one custody balance per currency with claims separate, and gates actions', async () => {
    mocks.custody.mockResolvedValue([
      {
        staff_member_id: STAFF_ID,
        currency: 'TZS',
        outstanding: '200000.0000',
        claimed_unverified_handovers: '90000.0000',
        pending_spending: '15000.0000',
        as_of: '2026-10-21T16:00:00Z',
      },
      {
        staff_member_id: STAFF_ID,
        currency: 'USD',
        outstanding: '40.0000',
        claimed_unverified_handovers: '0.0000',
        pending_spending: '0.0000',
        as_of: '2026-10-21T16:00:00Z',
      },
    ]);
    renderWithProviders(
      <CustodyTab timeZone="UTC" supervisor={SUPERVISOR} onSupervisorChange={vi.fn()} />,
      { tenantPermissions: READ },
    );
    const tzs = await screen.findByRole('region', { name: 'Custody in TZS' });
    expect(within(tzs).getByText('TZS 200,000.00')).toBeInTheDocument();
    expect(within(tzs).getByText('TZS 90,000.00')).toBeInTheDocument();
    const usd = screen.getByRole('region', { name: 'Custody in USD' });
    expect(within(usd).getByText('USD 40.00')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Record float' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Record handover' })).not.toBeInTheDocument();
  });

  it('lets office cash staff record a float for the selected supervisor', async () => {
    const user = userEvent.setup();
    mocks.custody.mockResolvedValue([]);
    mocks.issueFloat.mockResolvedValue({
      id: 'f1',
      staff_member_id: STAFF_ID,
      entry_type: 'FLOAT_ISSUED',
      amount: '50000',
      currency: 'TZS',
      occurred_at: '2026-10-21T06:00:00Z',
      reference: null,
      note: null,
    });
    renderWithProviders(
      <CustodyTab timeZone="UTC" supervisor={SUPERVISOR} onSupervisorChange={vi.fn()} />,
      { tenantPermissions: [...READ, P.tenantFinanceCash] },
    );
    await user.click(await screen.findByRole('button', { name: 'Record float' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /^Amount/ }), '50000');
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    await user.click(await within(dialog).findByRole('button', { name: 'Next' }));
    await user.click(await within(dialog).findByRole('button', { name: 'Record float' }));
    await waitFor(() => {
      expect(mocks.issueFloat).toHaveBeenCalledWith(
        expect.objectContaining({
          staff_member_id: STAFF_ID,
          entry_type: 'FLOAT_ISSUED',
          amount: '50000',
          currency: null,
        }),
        expect.any(String),
      );
    });
  });
});

describe('HandoversTab', () => {
  it('disables verification for the recorder and requires a reason to reject', async () => {
    const user = userEvent.setup();
    mocks.listHandovers.mockResolvedValue(
      page([makeHandover({ id: 'mine', reference: 'MINE', recorded_by: ME }), makeHandover()]),
    );
    mocks.decideHandover.mockResolvedValue(makeHandover({ status: 'REJECTED' }));
    renderWithProviders(<HandoversTab timeZone="UTC" />, {
      tenantPermissions: [...READ, P.tenantFinanceVerify],
    });
    await user.click(await screen.findByRole('button', { name: 'Actions for handover MINE' }));
    expect(screen.getByRole('menuitem', { name: /not allowed: you recorded it/ })).toHaveAttribute(
      'aria-disabled',
      'true',
    );
    await user.keyboard('{Escape}');
    await user.click(screen.getByRole('button', { name: 'Actions for handover SLIP-9' }));
    await user.click(screen.getByRole('menuitem', { name: 'Verify / reject' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Decision/ }));
    await user.click(await screen.findByRole('option', { name: 'Reject (not received)' }));
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }));
    expect(await within(dialog).findByText('A reason is required to reject')).toBeInTheDocument();
    await user.type(within(dialog).getByRole('textbox', { name: /Note/ }), 'Short by 10k');
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }));
    await waitFor(() => {
      expect(mocks.decideHandover).toHaveBeenCalledWith(
        makeHandover().id,
        { verified: false, note: 'Short by 10k' },
        expect.any(String),
      );
    });
  });
});
