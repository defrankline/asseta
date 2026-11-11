import type {
  PettyCashBalanceDto,
  PettyCashFundDto,
  PettyCashMovementDto,
  PettyCashStatementDto,
} from '../../../../api/pettyCashTypes';

/** The signed-in user of `renderWithProviders` (test/fixtures `makeMe`). */
export const ME = '33333333-3333-4333-8333-333333333333';
export const OTHER = '44444444-4444-4444-8444-444444444444';

export function makeBalance(o: Partial<PettyCashBalanceDto> = {}): PettyCashBalanceDto {
  return {
    fund_id: 'fund-1',
    fund_code: 'PC-01',
    fund_name: 'Office box',
    currency: 'TZS',
    holder_staff_id: 'staff-1',
    holder_staff_name: 'Asha Field',
    is_active: true,
    approved_limit: '500000.0000',
    low_balance_level: null,
    balance: '320000.0000',
    available_to_spend: '300000.0000',
    below_low_balance: false,
    funded: '500000.0000',
    spent: '180000.0000',
    returned: '0.0000',
    adjustments: '0.0000',
    written_off: '0.0000',
    advances_issued: '0.0000',
    advance_change_returned: '0.0000',
    pending_spending: '20000.0000',
    awaiting_acknowledgement: '0.0000',
    returns_claimed: '0.0000',
    open_return_differences: '0.0000',
    pending_adjustments: '0.0000',
    advances_outstanding: '0.0000',
    advance_spending: '0.0000',
    last_count_at: null,
    next_count_due_at: null,
    as_of: '2026-11-11T08:00:00Z',
    ...o,
  };
}

export function makeFund(o: Partial<PettyCashFundDto> = {}): PettyCashFundDto {
  return {
    id: 'fund-1',
    code: 'PC-01',
    name: 'Office box',
    holder_staff_id: 'staff-1',
    holder_staff_name: 'Asha Field',
    job_site_id: null,
    job_site_name: null,
    currency: 'TZS',
    approved_limit: '500000.0000',
    low_balance_level: null,
    note: null,
    is_active: true,
    version: 2,
    created_by: OTHER,
    created_by_name: 'Owner One',
    created_at: '2026-11-01T08:00:00Z',
    deactivated_at: null,
    deactivated_by: null,
    deactivated_by_name: null,
    deactivation_reason: null,
    pending_holder_change_id: null,
    balance: makeBalance(),
    ...o,
  };
}

export function makeMovement(o: Partial<PettyCashMovementDto> = {}): PettyCashMovementDto {
  return {
    id: 'mv-1',
    number: 'PC-000001',
    fund_id: 'fund-1',
    petty_cash_fund_name: 'Office box',
    kind: 'TOP_UP',
    status: 'PROPOSED',
    client_id: null,
    holder_staff_id: 'staff-1',
    holder_staff_name: 'Asha Field',
    amount: '180000.0000',
    currency: 'TZS',
    deposit_account_id: null,
    deposit_account_name: null,
    method: null,
    reference: null,
    note: null,
    suggested_amount: '180000.0000',
    cap_amount: '180000.0000',
    above_cap_reason: null,
    basis_from: null,
    evidence_attachment_ids: [],
    source: 'API',
    created_by: OTHER,
    created_by_name: 'Accountant One',
    created_at: '2026-11-10T08:00:00Z',
    client_created_at: null,
    decided_by: null,
    decided_by_name: null,
    decided_at: null,
    decision_note: null,
    issued_by: null,
    issued_by_name: null,
    issued_at: null,
    received_by: null,
    received_by_name: null,
    received_at: null,
    amount_received: null,
    receipt_method: null,
    receipt_note: null,
    variance_id: null,
    ...o,
  };
}

export function makeStatement(o: Partial<PettyCashStatementDto> = {}): PettyCashStatementDto {
  return {
    fund_id: 'fund-1',
    currency: 'TZS',
    timezone: 'Africa/Dar_es_Salaam',
    date_from: '2026-11-01',
    date_to: '2026-11-11',
    opening_balance: '0.0000',
    closing_balance: '320000.0000',
    lines: [
      {
        occurred_at: '2026-11-02T08:00:00Z',
        figure: 'funded',
        entity_type: 'petty_cash_movement',
        entity_id: 'mv-0',
        reference: 'PC-000000',
        note: null,
        money_in: '500000.0000',
        money_out: '0.0000',
        running_balance: '500000.0000',
      },
      {
        occurred_at: '2026-11-05T08:00:00Z',
        figure: 'spent',
        entity_type: 'expense',
        entity_id: 'exp-1',
        reference: null,
        note: 'Diesel for the pump',
        money_in: '0.0000',
        money_out: '180000.0000',
        running_balance: '320000.0000',
      },
    ],
    ...o,
  };
}

export const page = <T>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 25 });
