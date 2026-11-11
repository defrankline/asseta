import { screen, waitFor, within } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../../access/permissionCodes';
import { ApiError } from '../../../../api/ApiError';
import type { pettyCashService } from '../../../../api/services/pettyCashService';
import type { policyService } from '../../../../api/services/policyService';
import { renderWithProviders } from '../../../../test/renderWithProviders';
import { FieldPettyCashPage } from '../../field/FieldPettyCashPage';
import { PettyCashApprovals } from '../../approvals/PettyCashApprovals';
import { FundDetailPage } from './FundDetailPage';
import { PettyCashPage } from './PettyCashPage';
import { makeFund, makeMovement, makeStatement, ME, page } from './pettyCashFixtures';

const m = vi.hoisted(() => ({
  funds: vi.fn<typeof pettyCashService.funds>(),
  myFunds: vi.fn<typeof pettyCashService.myFunds>(),
  fund: vi.fn<typeof pettyCashService.fund>(),
  update: vi.fn<typeof pettyCashService.update>(),
  deactivate: vi.fn<typeof pettyCashService.deactivate>(),
  statement: vi.fn<typeof pettyCashService.statement>(),
  movements: vi.fn<typeof pettyCashService.movements>(),
  adjustments: vi.fn<typeof pettyCashService.adjustments>(),
  counts: vi.fn<typeof pettyCashService.counts>(),
  holderChanges: vi.fn<typeof pettyCashService.holderChanges>(),
  decideMovement: vi.fn<typeof pettyCashService.decideMovement>(),
  acknowledge: vi.fn<typeof pettyCashService.acknowledge>(),
  topUpSuggestion: vi.fn<typeof pettyCashService.topUpSuggestion>(),
  requestTopUp: vi.fn<typeof pettyCashService.requestTopUp>(),
  effective: vi.fn<typeof policyService.effective>(),
}));
vi.mock('../../../../api/services/pettyCashService', () => ({ pettyCashService: m }));
vi.mock('../../../../api/services/policyService', () => ({
  policyService: { effective: m.effective },
}));

const READ = [P.tenantPettyCashRead];
const MANAGER = [P.tenantPettyCashRead, P.tenantPettyCashManage, P.tenantPettyCashPropose];
const APPROVER = [P.tenantPettyCashRead, P.tenantPettyCashApprove];

function policy(values: Record<string, unknown> = {}) {
  return {
    policy_type: 'PETTY_CASH' as const,
    version_stamp: 'v1',
    values: { enabled: true, advances_enabled: false, ...values },
  };
}

async function menu(user: UserEvent, label: string, item: string) {
  await user.click(await screen.findByRole('button', { name: `Actions for ${label}` }));
  await user.click(await screen.findByRole('menuitem', { name: item }));
}

beforeEach(() => {
  vi.clearAllMocks();
  m.funds.mockResolvedValue(page([makeFund()]));
  m.myFunds.mockResolvedValue([]);
  m.fund.mockResolvedValue(makeFund());
  m.statement.mockResolvedValue(makeStatement());
  m.movements.mockResolvedValue(page([]));
  m.adjustments.mockResolvedValue(page([]));
  m.counts.mockResolvedValue(page([]));
  m.holderChanges.mockResolvedValue(page([]));
  m.effective.mockResolvedValue(policy());
});

describe('petty cash funds list', () => {
  it('lists funds with balance and available to spend; a reader gets no manage commands', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PettyCashPage />, { tenantPermissions: READ });
    expect(await screen.findByText('PC-01')).toBeInTheDocument();
    expect(screen.getByText('Asha Field')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New fund' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Actions for Office box' }));
    expect(screen.getByRole('menuitem', { name: 'View details' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Deactivate' })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Change holder' })).not.toBeInTheDocument();
  });

  it('hides the advances tab unless the policy switches advances on', async () => {
    renderWithProviders(<PettyCashPage />, { tenantPermissions: READ });
    expect(await screen.findByRole('tab', { name: 'Returns' })).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Advances' })).not.toBeInTheDocument();
  });

  it('edits a fund with the version that was read', async () => {
    const user = userEvent.setup();
    m.update.mockResolvedValue(makeFund({ version: 3, approved_limit: '600000.0000' }));
    renderWithProviders(<PettyCashPage />, { tenantPermissions: MANAGER });
    expect(await screen.findByRole('button', { name: 'New fund' })).toBeInTheDocument();
    await menu(user, 'Office box', 'Edit');
    expect(screen.getByRole('textbox', { name: /Code/ })).toHaveValue('PC-01');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    const limit = await screen.findByRole('textbox', { name: /Approved limit/ });
    await user.clear(limit);
    await user.type(limit, '600000');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Save changes' }));
    await waitFor(() => {
      expect(m.update).toHaveBeenCalledTimes(1);
    });
    expect(m.update.mock.calls[0]?.[0]).toBe('fund-1');
    expect(m.update.mock.calls[0]?.[1]).toMatchObject({
      code: 'PC-01',
      name: 'Office box',
      approved_limit: '600000',
      version: 2,
    });
  });

  it('shows the plain reason when a fund cannot be deactivated', async () => {
    const user = userEvent.setup();
    m.deactivate.mockRejectedValue(
      new ApiError({
        status: 422,
        code: 'PETTY_CASH_FUND_NOT_EMPTY',
        message: 'The fund still holds money',
        correlationId: null,
      }),
    );
    renderWithProviders(<PettyCashPage />, { tenantPermissions: MANAGER });
    await menu(user, 'Office box', 'Deactivate');
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /Reason/ }), 'Closing the office');
    await user.click(within(dialog).getByRole('button', { name: /Deactivate/ }));
    expect(await within(dialog).findByText(/only at a zero balance/)).toBeInTheDocument();
  });
});

describe('fund view', () => {
  it('shows the balance figures and the statement with a running balance', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/tenant/finance/petty-cash/funds/:id" element={<FundDetailPage />} />
      </Routes>,
      { tenantPermissions: MANAGER, route: '/tenant/finance/petty-cash/funds/fund-1' },
    );
    expect(await screen.findByText('Available to spend')).toBeInTheDocument();
    expect(screen.getByText('Spending waiting for approval')).toBeInTheDocument();
    const statement = await screen.findByRole('table', { name: 'Fund statement' });
    expect(within(statement).getByText('Diesel for the pump')).toBeInTheDocument();
    expect(within(statement).getByRole('link', { name: 'PC-000000' })).toHaveAttribute(
      'href',
      '/tenant/finance/petty-cash/movements/mv-0',
    );
    expect(m.statement).toHaveBeenCalledWith(
      'fund-1',
      { from: undefined, to: undefined },
      expect.anything(),
    );
  });
});

describe('petty cash approvals', () => {
  it('lets an approver decide someone else’s top-up', async () => {
    const user = userEvent.setup();
    m.movements.mockResolvedValue(page([makeMovement()]));
    m.decideMovement.mockResolvedValue(makeMovement({ status: 'APPROVED' }));
    renderWithProviders(<PettyCashApprovals />, { tenantPermissions: APPROVER });
    await menu(user, 'PC-000001', 'Approve / reject');
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Decision/ }));
    await user.click(await screen.findByRole('option', { name: 'Approve' }));
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }));
    await waitFor(() => {
      expect(m.decideMovement).toHaveBeenCalledWith(
        'mv-1',
        { approve: true, note: null },
        expect.any(String),
      );
    });
    expect(m.movements.mock.calls[0]?.[0].filters).toMatchObject({ status: 'PROPOSED' });
  });

  it('never offers the proposer an approve command for their own request', async () => {
    const user = userEvent.setup();
    m.movements.mockResolvedValue(page([makeMovement({ created_by: ME })]));
    renderWithProviders(<PettyCashApprovals />, { tenantPermissions: APPROVER });
    await user.click(await screen.findByRole('button', { name: 'Actions for PC-000001' }));
    expect(screen.getByRole('menuitem', { name: 'View details' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Approve / reject' })).not.toBeInTheDocument();
  });

  it('shows the server’s refusal cleanly', async () => {
    const user = userEvent.setup();
    m.movements.mockResolvedValue(page([makeMovement()]));
    m.decideMovement.mockRejectedValue(
      new ApiError({
        status: 403,
        code: 'SEGREGATION_OF_DUTIES',
        message: 'A proposal is approved by someone else',
        correlationId: null,
      }),
    );
    renderWithProviders(<PettyCashApprovals />, { tenantPermissions: APPROVER });
    await menu(user, 'PC-000001', 'Approve / reject');
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Decision/ }));
    await user.click(await screen.findByRole('option', { name: 'Approve' }));
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }));
    expect(
      await within(dialog).findByText(/A proposal is approved by someone else/),
    ).toBeInTheDocument();
  });
});

describe('field petty cash (holder)', () => {
  it('shows my funds and confirms money received with the amount counted', async () => {
    const user = userEvent.setup();
    m.myFunds.mockResolvedValue([makeFund()]);
    m.movements.mockResolvedValue(
      page([makeMovement({ status: 'ISSUED', issued_by_name: 'Office' })]),
    );
    m.acknowledge.mockResolvedValue(makeMovement({ status: 'ACKNOWLEDGED' }));
    renderWithProviders(<FieldPettyCashPage />, {
      tenantPermissions: [...READ, P.tenantExpenseWrite],
    });
    expect(await screen.findByRole('link', { name: 'PC-01 · Office box' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Record an expense' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Request a top-up' })).toBeInTheDocument();
    await menu(user, 'PC-000001', 'Confirm money received');
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Answer/ }));
    await user.click(await screen.findByRole('option', { name: /Received/ }));
    const amount = within(dialog).getByRole('textbox', { name: /Amount you counted/ });
    await user.clear(amount);
    await user.type(amount, '175000');
    await user.click(within(dialog).getByRole('button', { name: 'Record answer' }));
    await waitFor(() => {
      expect(m.acknowledge).toHaveBeenCalledWith(
        'mv-1',
        { acknowledged: true, amount_received: '175000', note: null },
        expect.any(String),
      );
    });
  });

  it('requests a top-up pre-filled with the imprest suggestion', async () => {
    const user = userEvent.setup();
    m.myFunds.mockResolvedValue([makeFund()]);
    m.topUpSuggestion.mockResolvedValue({
      fund_id: 'fund-1',
      currency: 'TZS',
      balance: '320000.0000',
      approved_limit: '500000.0000',
      in_flight: '0.0000',
      cap: '180000.0000',
      since: null,
      spending_since: '180000.0000',
      suggested: '180000.0000',
      expenses: [],
    });
    m.requestTopUp.mockResolvedValue(makeMovement());
    renderWithProviders(<FieldPettyCashPage />, { tenantPermissions: READ });
    await user.click(await screen.findByRole('button', { name: 'Request a top-up' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('textbox', { name: /Amount/ })).toHaveValue('180000.0000');
    await user.click(within(dialog).getByRole('button', { name: 'Send request' }));
    await waitFor(() => {
      expect(m.requestTopUp).toHaveBeenCalledTimes(1);
    });
    expect(m.requestTopUp.mock.calls[0]?.[1]).toMatchObject({
      amount: '180000.0000',
      above_cap_reason: null,
    });
  });

  it('says so when the caller holds no fund', async () => {
    renderWithProviders(<FieldPettyCashPage />, { tenantPermissions: READ });
    expect(await screen.findByText('You hold no petty cash fund')).toBeInTheDocument();
  });
});
