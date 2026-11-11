/** Form values, Yup rules and request bodies of the petty cash dialogs. Amounts stay decimal strings. */
import { array, mixed, object, string, type ObjectSchema } from 'yup';
import type { RemittanceMethod } from '../../../../api/custodyTypes';
import type {
  PettyCashAcknowledgementIn,
  PettyCashAdjustmentIn,
  PettyCashAdvanceIn,
  PettyCashCountIn,
  PettyCashFundDto,
  PettyCashFundIn,
  PettyCashFundingIn,
  PettyCashFundUpdateIn,
  PettyCashHolderChangeIn,
  PettyCashIssueIn,
  PettyCashReturnIn,
  TopUpRequestIn,
} from '../../../../api/pettyCashTypes';
import type { AttachmentDto } from '../../../../api/types';
import { compareDecimal, isDecimalString } from '../../../../utils/money';
import { positiveDecimalField } from '../../../platform/shared/validators';
import { optionalDecimal, optionalText, orNull, requiredDecimal } from '../../shared/formRules';

const evidence = (required: boolean) =>
  array(mixed<AttachmentDto>().required())
    .required()
    .max(20, 'At most 20 photos')
    .min(required ? 1 : 0, 'Your company policy needs a photo as evidence');

const ids = (list: readonly AttachmentDto[]) => list.map((a) => a.id);
const note = () => optionalText('Note', 1000);
const reference = () => optionalText('Reference', 120);
const method = () =>
  // Formik validates '' as undefined: "not stated" stays a valid, defined choice.
  mixed<RemittanceMethod | ''>()
    .oneOf(['', 'CASH_TO_OFFICE', 'BANK_DEPOSIT', 'MOBILE_MONEY'])
    .default('');

/** True when `a` (a valid decimal) is greater than `b`. */
export const above = (a: string, b: string): boolean =>
  isDecimalString(a.trim()) && isDecimalString(b) && compareDecimal(a.trim(), b) > 0;

// --- fund ---------------------------------------------------------------------------------------
export interface FundValues {
  code: string;
  name: string;
  holder_staff_id: string;
  job_site_id: string;
  currency: string;
  approved_limit: string;
  low_balance_level: string;
  note: string;
}

export const EMPTY_FUND: FundValues = {
  code: '',
  name: '',
  holder_staff_id: '',
  job_site_id: '',
  currency: '',
  approved_limit: '',
  low_balance_level: '',
  note: '',
};

export const fundValuesFrom = (f: PettyCashFundDto): FundValues => ({
  code: f.code,
  name: f.name,
  holder_staff_id: f.holder_staff_id,
  job_site_id: f.job_site_id ?? '',
  currency: f.currency,
  approved_limit: f.approved_limit,
  low_balance_level: f.low_balance_level ?? '',
  note: f.note ?? '',
});

/** `editing`: the holder changes through a holder change, never in the edit form. */
export const fundSchema = (editing: boolean): ObjectSchema<FundValues> =>
  object({
    code: string().trim().required('Code is required').max(32, 'At most 32 characters'),
    name: string().trim().required('Name is required').max(120, 'At most 120 characters'),
    holder_staff_id: editing ? string().ensure() : string().required('Choose who holds the fund'),
    job_site_id: string().ensure(),
    currency: string().ensure(),
    approved_limit: positiveDecimalField('Approved limit'),
    low_balance_level: optionalDecimal('Low-balance level').test(
      'below-limit',
      'The low-balance level must not be above the approved limit',
      function check(v) {
        const limit = (this.parent as FundValues).approved_limit;
        return v === '' || !above(v, limit);
      },
    ),
    note: note(),
  });

export const toFundPayload = (v: FundValues): PettyCashFundIn => ({
  code: v.code.trim(),
  name: v.name.trim(),
  holder_staff_id: v.holder_staff_id,
  job_site_id: orNull(v.job_site_id),
  currency: orNull(v.currency),
  approved_limit: v.approved_limit.trim(),
  low_balance_level: orNull(v.low_balance_level),
  note: orNull(v.note),
});

export const toFundUpdate = (v: FundValues, version: number): PettyCashFundUpdateIn => ({
  code: v.code.trim(),
  name: v.name.trim(),
  job_site_id: orNull(v.job_site_id),
  approved_limit: v.approved_limit.trim(),
  low_balance_level: orNull(v.low_balance_level),
  note: orNull(v.note),
  version,
});

// --- funding / top-up ---------------------------------------------------------------------------
export interface FundingValues {
  kind: 'FUNDING' | 'TOP_UP';
  amount: string;
  /** The cap (limit − balance − money on its way) the amount is checked against. */
  cap: string;
  above_cap_reason: string;
  deposit_account_id: string;
  method: RemittanceMethod | '';
  reference: string;
  note: string;
}

export const fundingSchema: ObjectSchema<FundingValues> = object({
  kind: mixed<'FUNDING' | 'TOP_UP'>().oneOf(['FUNDING', 'TOP_UP']).required(),
  amount: positiveDecimalField('Amount'),
  cap: string().ensure(),
  above_cap_reason: string()
    .trim()
    .ensure()
    .max(500, 'At most 500 characters')
    .test('reason', 'Give the reason for going above the fund’s limit', function check(v) {
      const p = this.parent as FundingValues;
      return !above(p.amount, p.cap) || v.length >= 3;
    }),
  deposit_account_id: string().ensure(),
  method: method(),
  reference: reference(),
  note: note(),
});

const capReason = (v: FundingValues) =>
  above(v.amount, v.cap) ? orNull(v.above_cap_reason) : null;

export const toFundingPayload = (
  v: FundingValues,
  fundId: string,
  clientId: string,
): PettyCashFundingIn => ({
  client_id: clientId,
  fund_id: fundId,
  kind: v.kind,
  amount: v.amount.trim(),
  deposit_account_id: orNull(v.deposit_account_id),
  method: v.method === '' ? null : v.method,
  reference: orNull(v.reference),
  note: orNull(v.note),
  above_cap_reason: capReason(v),
});

export const toTopUpRequest = (v: FundingValues, clientId: string): TopUpRequestIn => ({
  client_id: clientId,
  amount: v.amount.trim(),
  note: orNull(v.note),
  above_cap_reason: capReason(v),
});

// --- issue (hand over approved money) -----------------------------------------------------------
export interface IssueValues {
  deposit_account_id: string;
  method: RemittanceMethod | '';
  reference: string;
  evidence: AttachmentDto[];
  note: string;
}

export const issueSchema = (evidenceRequired: boolean): ObjectSchema<IssueValues> =>
  object({
    deposit_account_id: string().ensure(),
    method: method(),
    reference: reference(),
    evidence: evidence(evidenceRequired),
    note: note(),
  });

export const toIssuePayload = (v: IssueValues): PettyCashIssueIn => ({
  deposit_account_id: orNull(v.deposit_account_id),
  method: v.method === '' ? null : v.method,
  reference: orNull(v.reference),
  evidence_attachment_ids: ids(v.evidence),
  note: orNull(v.note),
});

// --- acknowledgement by the holder --------------------------------------------------------------
export interface AckValues {
  answer: 'ACKNOWLEDGE' | 'DISPUTE' | '';
  amount_received: string;
  note: string;
}

export const ACK_ANSWER_OPTIONS = [
  { value: 'ACKNOWLEDGE', label: 'Received (state the amount counted)' },
  { value: 'DISPUTE', label: 'Not received (dispute)' },
] as const;

export const ackSchema: ObjectSchema<AckValues> = object({
  answer: mixed<AckValues['answer']>()
    .oneOf(['ACKNOWLEDGE', 'DISPUTE'], 'Choose an answer')
    .required('Choose an answer'),
  amount_received: string()
    .trim()
    .ensure()
    .when('answer', {
      is: 'ACKNOWLEDGE',
      then: () => requiredDecimal('Amount received'),
    }),
  note: note().when('answer', {
    is: 'DISPUTE',
    then: (s) => s.min(3, 'Say what happened (at least 3 characters)'),
  }),
});

export const toAckPayload = (v: AckValues): PettyCashAcknowledgementIn =>
  v.answer === 'ACKNOWLEDGE'
    ? { acknowledged: true, amount_received: v.amount_received.trim(), note: orNull(v.note) }
    : { acknowledged: false, amount_received: null, note: orNull(v.note) };

// --- return -------------------------------------------------------------------------------------
export interface ReturnValues {
  amount: string;
  deposit_account_id: string;
  method: RemittanceMethod | '';
  reference: string;
  evidence: AttachmentDto[];
  note: string;
}

export const returnSchema = (evidenceRequired: boolean): ObjectSchema<ReturnValues> =>
  object({
    amount: positiveDecimalField('Amount'),
    deposit_account_id: string().ensure(),
    method: method(),
    reference: reference(),
    evidence: evidence(evidenceRequired),
    note: note(),
  });

export const toReturnPayload = (
  v: ReturnValues,
  fundId: string,
  clientId: string,
): PettyCashReturnIn => ({
  client_id: clientId,
  fund_id: fundId,
  amount: v.amount.trim(),
  deposit_account_id: orNull(v.deposit_account_id),
  method: v.method === '' ? null : v.method,
  reference: orNull(v.reference),
  note: orNull(v.note),
  evidence_attachment_ids: ids(v.evidence),
});

/** The office states what it counted; a note is optional. */
export interface AmountNoteValues {
  amount: string;
  note: string;
}

export const amountNoteSchema = (label: string): ObjectSchema<AmountNoteValues> =>
  object({ amount: requiredDecimal(label), note: note() });

// --- count / holder change ----------------------------------------------------------------------
export interface CountValues {
  counted_amount: string;
  witness_user_id: string;
  evidence: AttachmentDto[];
  note: string;
}

export const countSchema: ObjectSchema<CountValues> = object({
  counted_amount: requiredDecimal('Amount counted'),
  witness_user_id: string().ensure(),
  evidence: evidence(false),
  note: note(),
});

export const toCountPayload = (
  v: CountValues,
  fundId: string,
  clientId: string,
): PettyCashCountIn => ({
  client_id: clientId,
  fund_id: fundId,
  counted_amount: v.counted_amount.trim(),
  witness_user_id: orNull(v.witness_user_id),
  evidence_attachment_ids: ids(v.evidence),
  note: orNull(v.note),
});

export interface HolderChangeValues extends CountValues {
  to_staff_id: string;
}

export const holderChangeSchema: ObjectSchema<HolderChangeValues> = object({
  to_staff_id: string().required('Choose the new holder'),
  counted_amount: requiredDecimal('Amount counted at the change'),
  witness_user_id: string().ensure(),
  evidence: evidence(false),
  note: note(),
});

export const toHolderChangePayload = (v: HolderChangeValues): PettyCashHolderChangeIn => ({
  to_staff_id: v.to_staff_id,
  counted_amount: v.counted_amount.trim(),
  witness_user_id: orNull(v.witness_user_id),
  evidence_attachment_ids: ids(v.evidence),
  note: orNull(v.note),
});

// --- adjustment ---------------------------------------------------------------------------------
export interface AdjustmentValues {
  direction: 'RAISE' | 'LOWER';
  amount: string;
  reason_id: string;
  reason: string;
  evidence: AttachmentDto[];
}

export const ADJUSTMENT_DIRECTION_OPTIONS = [
  { value: 'RAISE', label: 'Raise the fund balance' },
  { value: 'LOWER', label: 'Lower the fund balance' },
] as const;

export const adjustmentSchema = (evidenceRequired: boolean): ObjectSchema<AdjustmentValues> =>
  object({
    direction: mixed<'RAISE' | 'LOWER'>().oneOf(['RAISE', 'LOWER']).required(),
    amount: positiveDecimalField('Amount'),
    reason_id: string().ensure(),
    reason: string()
      .trim()
      .required('Give the reason')
      .min(3, 'At least 3 characters')
      .max(500, 'At most 500 characters'),
    evidence: evidence(evidenceRequired),
  });

export const toAdjustmentPayload = (
  v: AdjustmentValues,
  fundId: string,
): PettyCashAdjustmentIn => ({
  fund_id: fundId,
  amount: v.direction === 'LOWER' ? `-${v.amount.trim()}` : v.amount.trim(),
  reason: v.reason.trim(),
  reason_id: orNull(v.reason_id),
  evidence_attachment_ids: ids(v.evidence),
});

// --- advance ------------------------------------------------------------------------------------
export interface AdvanceValues {
  recipient_staff_id: string;
  amount: string;
  purpose: string;
}

export const advanceSchema: ObjectSchema<AdvanceValues> = object({
  recipient_staff_id: string().required('Choose who receives the advance'),
  amount: positiveDecimalField('Amount'),
  purpose: string()
    .trim()
    .required('Say what the money is for')
    .min(3, 'At least 3 characters')
    .max(500, 'At most 500 characters'),
});

export const toAdvancePayload = (
  v: AdvanceValues,
  fundId: string,
  clientId: string,
): PettyCashAdvanceIn => ({
  client_id: clientId,
  fund_id: fundId,
  recipient_staff_id: v.recipient_staff_id,
  amount: v.amount.trim(),
  purpose: v.purpose.trim(),
});

/** Accept / decline (holder change) or a yes/no answer with an optional note. */
export interface AnswerValues {
  answer: 'YES' | 'NO' | '';
  note: string;
}

export const answerSchema: ObjectSchema<AnswerValues> = object({
  answer: mixed<AnswerValues['answer']>()
    .oneOf(['YES', 'NO'], 'Choose an answer')
    .required('Choose an answer'),
  note: note(),
});

/** How money moved (code-defined); empty = not stated. */
export const PETTY_METHOD_OPTIONS = [
  { value: '', label: 'Not stated' },
  { value: 'CASH_TO_OFFICE', label: 'Cash at the office' },
  { value: 'BANK_DEPOSIT', label: 'Bank transfer or deposit' },
  { value: 'MOBILE_MONEY', label: 'Mobile money' },
] as const;

/** Answer choices of the yes / no dialogs (holder change, cancel). */
export const ANSWER_CHOICES = {
  holderChange: [
    { value: 'YES', label: 'Take over the fund (I counted the cash)' },
    { value: 'NO', label: 'Decline' },
  ],
  cancel: [
    { value: 'YES', label: 'Cancel it (the current holder keeps the fund)' },
    { value: 'NO', label: 'Keep it waiting' },
  ],
} as const;
