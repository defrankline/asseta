import type { StatusTone } from '../../../../components/display/StatusChip';
import type {
  AdvanceStatus,
  CountReason,
  FundFigure,
  HolderChangeStatus,
  MovementKind,
  MovementStatus,
} from '../../../../api/pettyCashTypes';
import type { CashDecisionStatus } from '../../../../api/custodyTypes';
import { FINANCE_ERROR_HINTS } from '../../shared/financeDisplay';

/** Plain labels and tones of petty cash records (code-defined; neutral wording). */
export const MOVEMENT_KIND_LABELS: Readonly<Record<MovementKind, string>> = {
  FUNDING: 'Funding',
  TOP_UP: 'Top-up',
  RETURN: 'Return',
};

export const MOVEMENT_STATUS_LABELS: Readonly<Record<MovementStatus, string>> = {
  PROPOSED: 'Waiting for approval',
  APPROVED: 'Approved, to hand over',
  REJECTED: 'Rejected',
  ISSUED: 'Handed over, waiting for the holder',
  ACKNOWLEDGED: 'Received by the holder',
  DISPUTED: 'Disputed by the holder',
  CLAIMED: 'Waiting for the office count',
  CONFIRMED: 'Confirmed by the office',
};

export const MOVEMENT_STATUS_TONES: Readonly<Record<MovementStatus, StatusTone>> = {
  PROPOSED: 'warning',
  APPROVED: 'info',
  REJECTED: 'error',
  ISSUED: 'warning',
  ACKNOWLEDGED: 'success',
  DISPUTED: 'error',
  CLAIMED: 'warning',
  CONFIRMED: 'success',
};

/** Status filters of the fundings / top-ups list (ALL_CAPS constants for the dropdown guard). */
export const FUNDING_STATUS_OPTIONS: readonly { value: MovementStatus; label: string }[] = [
  { value: 'PROPOSED', label: 'Waiting for approval' },
  { value: 'APPROVED', label: 'Approved, to hand over' },
  { value: 'ISSUED', label: 'Waiting for the holder' },
  { value: 'ACKNOWLEDGED', label: 'Received' },
  { value: 'DISPUTED', label: 'Disputed' },
  { value: 'REJECTED', label: 'Rejected' },
];

export const RETURN_STATUS_OPTIONS: readonly { value: MovementStatus; label: string }[] = [
  { value: 'CLAIMED', label: 'Waiting for the office count' },
  { value: 'CONFIRMED', label: 'Confirmed' },
];

export const FUNDING_KIND_OPTIONS: readonly { value: 'FUNDING' | 'TOP_UP'; label: string }[] = [
  { value: 'FUNDING', label: 'Funding' },
  { value: 'TOP_UP', label: 'Top-up' },
];

export const DECISION_LABELS: Readonly<Record<CashDecisionStatus, string>> = {
  PENDING: 'Waiting for approval',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
};

export const DECISION_TONES: Readonly<Record<CashDecisionStatus, StatusTone>> = {
  PENDING: 'warning',
  APPROVED: 'success',
  REJECTED: 'error',
};

export const ADJUSTMENT_STATUS_OPTIONS: readonly { value: CashDecisionStatus; label: string }[] = [
  { value: 'PENDING', label: 'Waiting for approval' },
  { value: 'APPROVED', label: 'Approved' },
  { value: 'REJECTED', label: 'Rejected' },
];

export const HOLDER_CHANGE_LABELS: Readonly<Record<HolderChangeStatus, string>> = {
  PENDING: 'Waiting for the new holder',
  ACKNOWLEDGED: 'Taken over',
  DECLINED: 'Declined',
  CANCELLED: 'Cancelled',
};

export const HOLDER_CHANGE_TONES: Readonly<Record<HolderChangeStatus, StatusTone>> = {
  PENDING: 'warning',
  ACKNOWLEDGED: 'success',
  DECLINED: 'default',
  CANCELLED: 'default',
};

export const HOLDER_CHANGE_STATUS_OPTIONS: readonly {
  value: HolderChangeStatus;
  label: string;
}[] = [
  { value: 'PENDING', label: 'Waiting for the new holder' },
  { value: 'ACKNOWLEDGED', label: 'Taken over' },
  { value: 'DECLINED', label: 'Declined' },
  { value: 'CANCELLED', label: 'Cancelled' },
];

export const COUNT_REASON_LABELS: Readonly<Record<CountReason, string>> = {
  ROUTINE: 'Routine count',
  HOLDER_CHANGE: 'Count at a holder change',
};

export const ADVANCE_LABELS: Readonly<Record<AdvanceStatus, string>> = {
  OUTSTANDING: 'Not cleared yet',
  CLEARED: 'Cleared',
};

export const ADVANCE_TONES: Readonly<Record<AdvanceStatus, StatusTone>> = {
  OUTSTANDING: 'warning',
  CLEARED: 'success',
};

export const ADVANCE_STATUS_OPTIONS: readonly { value: AdvanceStatus; label: string }[] = [
  { value: 'OUTSTANDING', label: 'Not cleared yet' },
  { value: 'CLEARED', label: 'Cleared' },
];

/** What each ledger figure means, in plain words (fund view and statement). */
export const FIGURE_LABELS: Readonly<Record<FundFigure, string>> = {
  funded: 'Fundings and top-ups received',
  spent: 'Approved spending',
  returned: 'Returned to the office',
  adjustments: 'Approved adjustments',
  written_off: 'Written-off differences',
  advances_issued: 'Advances paid out',
  advance_change_returned: 'Change returned on advances',
  pending_spending: 'Spending waiting for approval',
  awaiting_acknowledgement: 'Handed over, not yet acknowledged',
  returns_claimed: 'Returns waiting for the office count',
  open_return_differences: 'Open return differences',
  pending_adjustments: 'Adjustments waiting for approval',
  advances_outstanding: 'Advances not cleared yet',
  advance_spending: 'Approved spending from advances',
};

/** Expense control flags (DEC-033), neutral wording: why a person should look at it. */
export const CONTROL_FLAG_LABELS: Readonly<Record<string, string>> = {
  OVERSPEND: 'More than the fund had available',
  SPENT_FROM_COLLECTIONS: 'Paid from collected cash',
  ABOVE_PETTY_CASH_MAXIMUM: 'Above the per-expense maximum',
};

/** The expense list's "To look at" filter (listExpenses `control_flag`). */
export const CONTROL_FLAG_OPTIONS: readonly { value: string; label: string }[] = [
  { value: 'OVERSPEND', label: 'More than the fund had available' },
  { value: 'SPENT_FROM_COLLECTIONS', label: 'Paid from collected cash' },
  { value: 'ABOVE_PETTY_CASH_MAXIMUM', label: 'Above the per-expense maximum' },
];

export const controlFlagLabel = (flag: string): string => CONTROL_FLAG_LABELS[flag] ?? flag;

/** Stable server codes of petty cash requests → what the user can do (shown with the message). */
export const PETTY_CASH_ERROR_HINTS: Readonly<Record<string, string>> = {
  ...FINANCE_ERROR_HINTS,
  SEGREGATION_OF_DUTIES:
    'Someone else must do this: the person who proposed it, and the fund’s holder, cannot approve or hand over money for it.',
  NOT_FUND_HOLDER: 'Only the fund’s holder can do this.',
  PETTY_CASH_DISABLED: 'Petty cash is switched off for your organisation.',
  PETTY_CASH_FUND_NOT_FOUND: 'This fund was not found, or you do not hold it.',
  PETTY_CASH_FUND_INACTIVE: 'This fund is inactive. Reactivate it first.',
  PETTY_CASH_FUND_NOT_EMPTY:
    'A fund is deactivated only at a zero balance. Return or adjust the money first.',
  PETTY_CASH_FUND_BUSY:
    'Something is still waiting on this fund (spending, money on its way, a return or an adjustment). Finish it first.',
  PETTY_CASH_FUND_REQUIRED: 'Choose the petty cash fund that paid.',
  PETTY_CASH_FUND_NOT_ALLOWED: 'A fund applies only to expenses paid from petty cash.',
  PETTY_CASH_CURRENCY_MISMATCH: 'The expense must be in the fund’s currency.',
  PETTY_CASH_INSUFFICIENT: 'This is more than the fund has available to spend now.',
  PETTY_CASH_ABOVE_CAP_REASON_REQUIRED:
    'This amount takes the fund above its limit; give the reason.',
  PETTY_CASH_NOTHING_TO_TOP_UP:
    'Nothing to top up: no approved spending since the last top-up, or the fund is at its limit.',
  PETTY_CASH_ALREADY_DECIDED: 'Someone already decided this. Reload to see it.',
  PETTY_CASH_ALREADY_ACKNOWLEDGED: 'This was already answered. Reload to see it.',
  PETTY_CASH_ALREADY_CONFIRMED: 'This return was already confirmed. Reload to see it.',
  PETTY_CASH_NOT_APPROVED: 'Only approved money is handed over.',
  PETTY_CASH_SAME_HOLDER: 'This person already holds the fund.',
  PETTY_CASH_HOLDER_CHANGE_PENDING: 'A holder change is already waiting for this fund.',
  PETTY_CASH_WITNESS_INVALID:
    'The witness must be someone else who holds the petty cash count permission.',
  PETTY_CASH_ADVANCES_DISABLED: 'Cash advances are switched off for your organisation.',
  PETTY_CASH_ADVANCE_TO_HOLDER: 'An advance goes to someone other than the fund’s holder.',
  PETTY_CASH_ADVANCE_EXPENSES_PENDING:
    'Some expenses of this advance still wait for a decision. Clear it once they are decided.',
  PETTY_CASH_ADVANCE_CLEARED: 'This advance is already cleared.',
  PETTY_CASH_ADVANCE_NOT_FOUND: 'Choose an advance of this fund that is not cleared yet.',
  DEPOSIT_ACCOUNT_CURRENCY_MISMATCH: 'Choose a company account in the fund’s currency.',
  SPENDING_FROM_COLLECTIONS_NOT_ALLOWED:
    'Your organisation does not allow paying expenses from collected cash. Pay from a petty cash fund or the company.',
  STALE_VERSION: 'Someone changed this fund meanwhile. Reload it and try again.',
};

export const FUND_DEACTIVATE_CONSEQUENCES =
  'Nobody can spend from it or fund it while inactive. Its records and statement are kept.';
