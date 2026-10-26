/** Plain-English labels, tones, filter options and error hints for customer hours screens. */
import type {
  BillingMode,
  HoursPurchaseDto,
  ReasonCodeDto,
  HoursPurchaseStatus,
  LedgerEntryType,
  ProposalStatus,
  ReasonKind,
  RequestStatus,
} from '../../../api/hoursTypes';
import {
  LEDGER_ENTRY_TYPES,
  PROPOSAL_STATUSES,
  PURCHASE_STATUSES,
  REASON_KINDS,
  REQUEST_STATUSES,
} from '../../../api/services/hoursSchemas';
import type { StatusTone } from '../../../components/display/StatusChip';
import type { CustomerPaymentDto } from '../../../api/types';
import { formatMoney } from '../../../utils/money';
import type { Option } from '../shared/display';
import { FINANCE_ERROR_HINTS, SETTLEMENT_LABELS } from '../shared/financeDisplay';

/** Shown on a disabled decide button for your own proposal / request (server enforces it too). */
export const OWN_REQUEST_TEXT = 'Someone else must decide your own request';

export const PURCHASE_STATUS_LABELS: Readonly<Record<HoursPurchaseStatus, string>> = {
  AWAITING_PAYMENT: 'Awaiting payment',
  PARTLY_ACTIVE: 'Partly active',
  ACTIVE: 'Active',
  CONSUMED: 'Used up',
  EXPIRED: 'Expired',
  CANCELLED: 'Cancelled',
};
export const PURCHASE_STATUS_TONES: Readonly<Record<HoursPurchaseStatus, StatusTone>> = {
  AWAITING_PAYMENT: 'warning',
  PARTLY_ACTIVE: 'info',
  ACTIVE: 'success',
  CONSUMED: 'default',
  EXPIRED: 'default',
  CANCELLED: 'default',
};
export const PURCHASE_STATUS_OPTIONS: readonly Option<HoursPurchaseStatus>[] =
  PURCHASE_STATUSES.map((s) => ({ value: s, label: PURCHASE_STATUS_LABELS[s] }));

export const LEDGER_TYPE_LABELS: Readonly<Record<LedgerEntryType, string>> = {
  ACTIVATED: 'Activated',
  CONSUMED: 'Used on a job',
  TRANSFER_OUT: 'Transferred out',
  TRANSFER_IN: 'Transferred in',
  EXPIRED: 'Expired',
  REVERSAL: 'Reversed',
  PROVISIONAL: 'Used today (provisional)',
  PROVISIONAL_REVERSED: 'Provisional use given back',
};
export const LEDGER_TYPE_OPTIONS: readonly Option<LedgerEntryType>[] = LEDGER_ENTRY_TYPES.map(
  (t) => ({ value: t, label: LEDGER_TYPE_LABELS[t] }),
);

export const REQUEST_STATUS_LABELS: Readonly<Record<RequestStatus, string>> = {
  PENDING: 'Awaiting decision',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  WITHDRAWN: 'Withdrawn',
};
export const REQUEST_STATUS_TONES: Readonly<Record<RequestStatus, StatusTone>> = {
  PENDING: 'warning',
  APPROVED: 'success',
  REJECTED: 'error',
  WITHDRAWN: 'default',
};
export const REQUEST_STATUS_OPTIONS: readonly Option<RequestStatus>[] = REQUEST_STATUSES.map(
  (s) => ({ value: s, label: REQUEST_STATUS_LABELS[s] }),
);

export const PROPOSAL_STATUS_LABELS: Readonly<Record<ProposalStatus, string>> = {
  PROPOSED: 'Awaiting decision',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  WITHDRAWN: 'Withdrawn',
  REVOKED: 'Revoked',
};
export const PROPOSAL_STATUS_TONES: Readonly<Record<ProposalStatus, StatusTone>> = {
  PROPOSED: 'warning',
  APPROVED: 'success',
  REJECTED: 'error',
  WITHDRAWN: 'default',
  REVOKED: 'default',
};
export const PROPOSAL_STATUS_OPTIONS: readonly Option<ProposalStatus>[] = PROPOSAL_STATUSES.map(
  (s) => ({ value: s, label: PROPOSAL_STATUS_LABELS[s] }),
);

export const REASON_KIND_LABELS: Readonly<Record<ReasonKind, string>> = {
  DISCOUNT: 'Discount',
  CREDIT: 'Credit',
  TRANSFER: 'Transfer',
  CANCELLATION: 'Cancellation',
};
export const REASON_KIND_OPTIONS: readonly Option<ReasonKind>[] = REASON_KINDS.map((k) => ({
  value: k,
  label: REASON_KIND_LABELS[k],
}));

export const BILLING_MODE_LABELS: Readonly<Record<BillingMode, string>> = {
  INVOICE: 'Invoice after the work',
  PREPAID_HOURS: 'Prepaid customer hours',
};

export const CANCELLED_OPTIONS: readonly Option[] = [
  { value: 'false', label: 'Not cancelled' },
  { value: 'true', label: 'Cancelled' },
];

export const HOURS_ERROR_HINTS: Readonly<Record<string, string>> = {
  ...FINANCE_ERROR_HINTS,
  SEGREGATION_OF_DUTIES: OWN_REQUEST_TEXT + '. Ask another authorised colleague.',
  HOURS_DISABLED: 'Customer hours are switched off in your company policy.',
  WALK_IN_NOT_ALLOWED: 'Walk-in customers are not allowed by your company policy.',
  WALK_IN: 'Choose an existing customer or enter a walk-in, not both.',
  BILLING_MODE_NOT_ALLOWED: 'This billing method is not allowed by your company policy.',
  NO_RATE: 'No rate card covers this machine; add a rate card first.',
  CUSTOMER_INACTIVE: 'The customer is inactive.',
  MACHINE_INACTIVE: 'The machine is retired; choose an active machine.',
  SITE_INACTIVE: 'The job site is inactive.',
  DUPLICATE_CUSTOMER: 'A customer with these details already exists.',
  ALREADY_REGISTERED: 'This customer is already registered.',
  PAYMENT_NOT_PERMITTED: 'You may not record a payment with this purchase.',
  NOTHING_TO_PAY: 'Nothing is left to pay on this purchase.',
  CREDIT_NOT_ALLOWED: 'Credit is not allowed by your company policy.',
  NO_CREDIT_ARRANGEMENT: 'The customer has no approved credit arrangement in effect.',
  CREDIT_LIMIT_EXCEEDED: 'This would exceed the customer’s available credit.',
  EXCEEDS_UNACTIVATED_HOURS: 'Activate no more than the hours still awaiting activation.',
  EXCEEDS_REMAINING_HOURS: 'Transfer no more than the hours remaining on that machine.',
  SAME_MACHINE: 'Choose a different machine to transfer to.',
  PURCHASE_CANCELLED: 'This purchase is cancelled.',
  PURCHASE_HAS_CONSUMPTION:
    'Hours were already used from this purchase, so it cannot be cancelled.',
  CANCELLATION_PENDING: 'A cancellation is already awaiting a decision.',
  DISCOUNT_ABOVE_MAXIMUM: 'The discount is above the highest your company policy allows.',
  OVERLAPPING_ARRANGEMENT: 'Another arrangement already covers these dates.',
  ALREADY_DECIDED: 'Someone already decided this. Reload to see it.',
  NOT_PROPOSED: 'Only proposals awaiting a decision can be changed.',
  NOT_APPROVED: 'Only approved records can be revoked.',
  NOT_PROPOSER: 'Only the person who proposed it can change or withdraw it.',
  NOT_REQUESTER: 'Only the person who requested it can withdraw it.',
  REASON_CODE_REQUIRED: 'Choose a reason from your company list.',
  REASON_CODE_INACTIVE: 'That reason is no longer in use; choose another.',
  REASON_CODE_NOT_FOUND: 'That reason was not found; choose another.',
  DUPLICATE_REASON_CODE: 'A reason with this code already exists.',
  ATTACHMENT_NOT_FOUND: 'The evidence file was not found; upload it again.',
};

/** Hours as shown to people: the decimal string with an `h` suffix. */
export const hoursText = (value: string): string => `${value} h`;

/** Picker option labels. */
export const reasonCodeLabel = (r: ReasonCodeDto): string => `${r.code} · ${r.label}`;
export const purchaseLabel = (p: HoursPurchaseDto): string =>
  `${p.purchase_number} · ${p.hours} h · ${PURCHASE_STATUS_LABELS[p.status]}`;
export const paymentLabel = (p: CustomerPaymentDto): string =>
  `${formatMoney(p.amount, p.currency)} · ${p.reference ?? p.method} · ${SETTLEMENT_LABELS[p.status]}`;
