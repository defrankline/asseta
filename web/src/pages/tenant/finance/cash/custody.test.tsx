import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../../access/permissionCodes';
import type { cashService } from '../../../../api/services/cashService';
import type { custodyService } from '../../../../api/services/custodyService';
import type { policyService } from '../../../../api/services/policyService';
import type {
  CashReasonDto,
  CashRetentionDto,
  CashTransferDto,
  CashVarianceDto,
  CustodianDto,
} from '../../../../api/custodyTypes';
import {
  makeDay,
  ME,
  OTHER_USER,
  page,
  STAFF_ID,
  SUPERVISOR,
} from '../../../../test/financeFixtures';
import { renderWithProviders } from '../../../../test/renderWithProviders';
import { CashReasonsTab } from './CashReasonsTab';
import { ReconciliationTab } from './ReconciliationTab';
import { RetentionsTab } from './RetentionsTab';
import { TransfersTab } from './TransfersTab';
import { VariancesTab } from './VariancesTab';

const RECEIVER_ID = '55555555-0000-4000-8000-000000000002';

const m = vi.hoisted(() => ({
  custodians: vi.fn<typeof custodyService.custodians>(),
  transfers: vi.fn<typeof custodyService.transfers>(),
  transfer: vi.fn<typeof custodyService.transfer>(),
  acknowledgeTransfer: vi.fn<typeof custodyService.acknowledgeTransfer>(),
  variances: vi.fn<typeof custodyService.variances>(),
  variance: vi.fn<typeof custodyService.variance>(),
  decideWriteOff: vi.fn<typeof custodyService.decideWriteOff>(),
  retentions: vi.fn<typeof custodyService.retentions>(),
  reasons: vi.fn<typeof custodyService.reasons>(),
  createReason: vi.fn<typeof custodyService.createReason>(),
  transactions: vi.fn<typeof custodyService.transactions>(),
  effective: vi.fn<typeof policyService.effective>(),
  reconciliation: vi.fn<typeof cashService.reconciliation>(),
}));
vi.mock('../../../../api/services/custodyService', () => ({ custodyService: m }));
vi.mock('../../../../api/services/policyService', () => ({
  policyService: { effective: m.effective },
}));
vi.mock('../../../../api/services/cashService', () => ({
  cashService: { reconciliation: m.reconciliation },
}));

const CUSTODIANS: CustodianDto[] = [
  {
    staff_member_id: STAFF_ID,
    full_name: 'Sam Supervisor',
    kind: 'SUPERVISOR',
    employee_code: null,
    is_active: true,
    has_login: true,
  },
  {
    staff_member_id: RECEIVER_ID,
    full_name: 'Omari Operator',
    kind: 'OPERATOR',
    employee_code: 'OP-7',
    is_active: true,
    has_login: false,
  },
];

function cashPolicy(values: Record<string, unknown> = {}) {
  return {
    policy_type: 'CASH_CUSTODY' as const,
    version_stamp: 'v1',
    values: {
      recorders_may_record_for_others: false,
      transfer_ack_required: true,
      recorder_receiver_counts_as_ack: true,
      float_ack_required: true,
      remit_full_balance: true,
      writeoff_requires_approval: true,
      retention_allowed: true,
      ...values,
    },
  };
}

function makeTransfer(o: Partial<CashTransferDto> = {}): CashTransferDto {
  return {
    id: 'tttttttt-0000-4000-8000-000000000001',
    client_id: null,
    from_staff_id: STAFF_ID,
    from_staff_name: 'Sam Supervisor',
    to_staff_id: RECEIVER_ID,
    to_staff_name: 'Omari Operator',
    amount_declared: '100000.0000',
    currency: 'TZS',
    transferred_at: '2026-10-21T08:00:00Z',
    note: null,
    status: 'PENDING_ACKNOWLEDGEMENT',
    source: 'WEB',
    recorded_by: OTHER_USER,
    recorded_at: '2026-10-21T08:00:00Z',
    amount_received: null,
    ack_method: null,
    acknowledged_by: null,
    acknowledged_at: null,
    ack_note: null,
    variance_id: null,
    ...o,
  };
}

function makeVariance(o: Partial<CashVarianceDto> = {}): CashVarianceDto {
  return {
    id: 'vvvvvvvv-0000-4000-8000-000000000001',
    source_type: 'TRANSFER',
    source_id: 'tttttttt-0000-4000-8000-000000000001',
    staff_member_id: STAFF_ID,
    staff_member_name: 'Sam Supervisor',
    counterparty_staff_id: RECEIVER_ID,
    currency: 'TZS',
    declared_amount: '100000.0000',
    received_amount: '90000.0000',
    amount: '10000.0000',
    case_id: null,
    opened_at: '2026-10-21T09:00:00Z',
    opened_by: null,
    status: 'WRITE_OFF_PROPOSED',
    reason_id: null,
    proposed_by: OTHER_USER,
    proposed_at: '2026-10-21T10:00:00Z',
    proposal_note: 'Counted twice',
    outcome: null,
    resolved_by: null,
    resolved_at: null,
    resolution_note: null,
    ...o,
  };
}

function makeRetention(o: Partial<CashRetentionDto> = {}): CashRetentionDto {
  return {
    id: 'rrrrrrrr-0000-4000-8000-000000000001',
    staff_member_id: STAFF_ID,
    staff_member_name: 'Sam Supervisor',
    amount: '20000.0000',
    currency: 'TZS',
    reason_id: null,
    reason: 'Fuel float for the weekend',
    valid_until: null,
    status: 'PENDING',
    created_by: ME,
    created_at: '2026-10-21T09:00:00Z',
    decided_by: null,
    decided_at: null,
    decision_note: null,
    ...o,
  };
}

beforeEach(() => {
  m.custodians.mockResolvedValue(page(CUSTODIANS));
  m.effective.mockResolvedValue(cashPolicy());
});

describe('TransfersTab', () => {
  it('lets the receiver acknowledge the amount actually received', async () => {
    const user = userEvent.setup();
    m.transfers.mockResolvedValue(page([makeTransfer()]));
    m.acknowledgeTransfer.mockResolvedValue(
      makeTransfer({ status: 'ACKNOWLEDGED', amount_received: '90000.0000', variance_id: 'v1' }),
    );
    renderWithProviders(<TransfersTab timeZone="UTC" field />, {
      tenantPermissions: [P.tenantCollectionRecord],
    });
    const actions = await screen.findByRole('button', {
      name: 'Actions for transfer Sam Supervisor to Omari Operator',
    });
    expect(m.transfers).toHaveBeenCalledWith(
      expect.objectContaining({
        filters: expect.objectContaining({ status: 'PENDING_ACKNOWLEDGEMENT' }) as unknown,
      }),
      expect.any(AbortSignal),
    );
    await user.click(actions);
    await user.click(screen.getByRole('menuitem', { name: 'Acknowledge / dispute' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Answer/ }));
    await user.click(await screen.findByRole('option', { name: 'Acknowledge (cash received)' }));
    const amount = within(dialog).getByRole('textbox', { name: /Amount actually received/ });
    await user.clear(amount);
    await user.type(amount, '90000');
    await user.click(within(dialog).getByRole('button', { name: 'Record answer' }));
    await waitFor(() => {
      expect(m.acknowledgeTransfer).toHaveBeenCalledWith(
        makeTransfer().id,
        { acknowledged: true, amount_received: '90000', note: null },
        expect.any(String),
      );
    });
    expect(
      await screen.findByText('Transfer acknowledged; the difference was opened as a variance.'),
    ).toBeInTheDocument();
  });

  it('does not let the recorder answer their own transfer', async () => {
    const user = userEvent.setup();
    m.transfers.mockResolvedValue(page([makeTransfer({ recorded_by: ME })]));
    renderWithProviders(<TransfersTab timeZone="UTC" />, {
      tenantPermissions: [P.tenantCollectionRecord],
    });
    await user.click(
      await screen.findByRole('button', {
        name: 'Actions for transfer Sam Supervisor to Omari Operator',
      }),
    );
    expect(screen.getByRole('menuitem', { name: 'Acknowledge / dispute' })).toHaveAttribute(
      'aria-disabled',
      'true',
    );
  });
});

describe('VariancesTab', () => {
  it('disables deciding your own write-off proposal, with the reason', async () => {
    const user = userEvent.setup();
    m.variances.mockResolvedValue(page([makeVariance({ proposed_by: ME })]));
    renderWithProviders(<VariancesTab timeZone="UTC" initialStatus="WRITE_OFF_PROPOSED" />, {
      tenantPermissions: [P.tenantFinanceRead, P.tenantFinanceWriteoff],
    });
    await user.click(
      await screen.findByRole('button', { name: 'Actions for variance of Sam Supervisor' }),
    );
    expect(
      screen.getByRole('menuitem', { name: /Someone else must decide your own request/ }),
    ).toHaveAttribute('aria-disabled', 'true');
  });

  it("approves someone else's write-off proposal", async () => {
    const user = userEvent.setup();
    m.variances.mockResolvedValue(page([makeVariance()]));
    m.decideWriteOff.mockResolvedValue(
      makeVariance({ status: 'RESOLVED', outcome: 'WRITTEN_OFF' }),
    );
    renderWithProviders(<VariancesTab timeZone="UTC" initialStatus="WRITE_OFF_PROPOSED" />, {
      tenantPermissions: [P.tenantFinanceRead, P.tenantFinanceWriteoff],
    });
    await user.click(
      await screen.findByRole('button', { name: 'Actions for variance of Sam Supervisor' }),
    );
    await user.click(screen.getByRole('menuitem', { name: 'Approve / reject write-off' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Decision/ }));
    await user.click(await screen.findByRole('option', { name: 'Approve' }));
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }));
    await waitFor(() => {
      expect(m.decideWriteOff).toHaveBeenCalledWith(
        makeVariance().id,
        { approve: true, note: null },
        expect.any(String),
      );
    });
  });
});

describe('RetentionsTab', () => {
  it('hides requests when the tenant does not allow keeping cash', async () => {
    m.effective.mockResolvedValue(cashPolicy({ retention_allowed: false }));
    m.retentions.mockResolvedValue(page([]));
    renderWithProviders(<RetentionsTab timeZone="UTC" field />, {
      tenantPermissions: [P.tenantCollectionRecord],
    });
    expect(
      await screen.findByText(/does not allow keeping cash: everything collected is remitted/),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Request to keep cash' })).not.toBeInTheDocument();
  });

  it('disables approving your own request', async () => {
    const user = userEvent.setup();
    m.retentions.mockResolvedValue(page([makeRetention()]));
    renderWithProviders(<RetentionsTab timeZone="UTC" />, {
      tenantPermissions: [P.tenantFinanceRead, P.tenantFinanceRetentionApprove],
    });
    await user.click(
      await screen.findByRole('button', { name: 'Actions for retention of Sam Supervisor' }),
    );
    expect(
      screen.getByRole('menuitem', { name: /Someone else must decide your own request/ }),
    ).toHaveAttribute('aria-disabled', 'true');
  });
});

describe('CashReasonsTab', () => {
  it('creates a reason in the chosen list', async () => {
    const user = userEvent.setup();
    const created: CashReasonDto = {
      id: 'reason-1',
      kind: 'WRITE_OFF',
      label: 'Counting error',
      description: null,
      is_active: true,
      version: 1,
      created_at: '2026-10-21T09:00:00Z',
      deactivated_at: null,
      deactivation_reason: null,
    };
    m.reasons.mockResolvedValue(page([]));
    m.createReason.mockResolvedValue(created);
    renderWithProviders(<CashReasonsTab timeZone="UTC" />, {
      tenantPermissions: [P.tenantFinanceRead, P.tenantFinanceReasonManage],
    });
    await user.click(await screen.findByRole('button', { name: 'New reason' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /List/ }));
    await user.click(await screen.findByRole('option', { name: 'Write-off' }));
    await user.type(within(dialog).getByRole('textbox', { name: /Label/ }), 'Counting error');
    await user.click(within(dialog).getByRole('button', { name: 'Create' }));
    await waitFor(() => {
      expect(m.createReason).toHaveBeenCalledWith(
        { kind: 'WRITE_OFF', label: 'Counting error', description: null },
        expect.any(String),
      );
    });
  });
});

describe('ReconciliationTab drill-down (3.4.8)', () => {
  it('opens the transactions behind a figure', async () => {
    const user = userEvent.setup();
    m.reconciliation.mockResolvedValue({
      staff_member_id: STAFF_ID,
      currency: 'TZS',
      timezone: 'UTC',
      days: [makeDay({ day: '2026-10-21', transfers_in: '25000.0000' })],
    });
    m.transactions.mockResolvedValue(
      page([
        {
          figure: 'transfers_in',
          occurred_at: '2026-10-21T08:00:00Z',
          amount: '25000.0000',
          currency: 'TZS',
          entity_type: 'cash_transfer',
          entity_id: 'tttttttt-0000-4000-8000-000000000001',
          status: 'ACKNOWLEDGED',
          reference: null,
          note: 'From the site office',
          recorded_by: null,
          counterparty_staff_id: RECEIVER_ID,
        },
      ]),
    );
    renderWithProviders(
      <ReconciliationTab supervisor={SUPERVISOR} onSupervisorChange={vi.fn()} />,
      {
        tenantPermissions: [P.tenantFinanceRead, P.tenantStaffRead],
      },
    );
    const card = await screen.findByRole('region', { name: 'Reconciliation 2026-10-21' });
    await user.click(
      within(card).getByRole('button', { name: 'Transfers received: show the transactions' }),
    );
    expect(await screen.findByText('From the site office')).toBeInTheDocument();
    expect(m.transactions).toHaveBeenCalledWith(
      expect.objectContaining({
        staffMemberId: STAFF_ID,
        from: '2026-10-21',
        to: '2026-10-21',
        currency: 'TZS',
        figure: 'transfers_in',
      }),
      expect.any(AbortSignal),
    );
    expect(screen.getByRole('link', { name: 'Transfer' })).toHaveAttribute(
      'href',
      '/tenant/finance/cash?tab=transfers&id=tttttttt-0000-4000-8000-000000000001',
    );
  });
});
