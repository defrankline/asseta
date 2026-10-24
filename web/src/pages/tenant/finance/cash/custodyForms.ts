/** Form values, validation and request bodies of the cash custody chain dialogs. Amounts stay strings. */
import { mixed, object, string, type ObjectSchema } from 'yup';
import type {
  CashAcknowledgementIn,
  CashReasonIn,
  CashReasonKind,
  CashRetentionIn,
  CashTransferIn,
  CustodyAdjustmentIn,
  CustodyAdjustmentKind,
  RemittanceDecisionIn,
  SyncResolutionIn,
  SyncResolutionOutcome,
  VarianceOutcome,
  VarianceResolutionIn,
  WriteOffProposalIn,
} from '../../../../api/custodyTypes';
import { isZeroDecimal } from '../../../../utils/money';
import {
  positiveDecimalField,
  reasonField,
  signedDecimalField,
} from '../../../platform/shared/validators';
import {
  optionalDecimal,
  optionalInstant,
  optionalText,
  orNull,
  requiredInstant,
} from '../../shared/formRules';
import type { ReversibleEntity } from './custodyDisplay';

// --- transfer -------------------------------------------------------------------------------------------
export interface TransferValues {
  from_staff_id: string;
  to_staff_id: string;
  amount: string;
  currency: string;
  transferred_at: string;
  note: string;
  amount_received: string;
}

export const transferSchema: ObjectSchema<TransferValues> = object({
  from_staff_id: string().ensure(),
  to_staff_id: string()
    .required('Choose who received the cash')
    .test('differs', 'The sender and the receiver must be different people', function differs(v) {
      const from = (this.parent as TransferValues).from_staff_id;
      return from === '' || v !== from;
    }),
  amount: positiveDecimalField('Amount handed over'),
  currency: string().ensure(),
  transferred_at: requiredInstant('Handed over at'),
  note: optionalText('Note', 1000),
  amount_received: optionalDecimal('Amount actually received'),
});

export function toTransferPayload(v: TransferValues, clientId: string): CashTransferIn {
  return {
    client_id: clientId,
    from_staff_id: orNull(v.from_staff_id),
    to_staff_id: v.to_staff_id,
    amount: v.amount.trim(),
    currency: orNull(v.currency),
    transferred_at: v.transferred_at,
    note: orNull(v.note),
    amount_received: orNull(v.amount_received),
  };
}

// --- acknowledgement (transfer or float) and remittance decision ----------------------------------------
export type AckDecision = 'ACKNOWLEDGE' | 'DISPUTE' | '';

export interface AckValues {
  decision: AckDecision;
  amount_received: string;
  note: string;
}

export const ackSchema: ObjectSchema<AckValues> = object({
  decision: mixed<AckDecision>()
    .oneOf(['ACKNOWLEDGE', 'DISPUTE'], 'Choose an answer')
    .required('Choose an answer'),
  amount_received: string()
    .trim()
    .ensure()
    .when('decision', {
      is: 'ACKNOWLEDGE',
      then: (s) =>
        s
          .required('Enter the amount actually received')
          .matches(/^\d+(\.\d{1,4})?$/, 'Enter a number with at most 4 decimal places'),
    }),
  note: string()
    .trim()
    .ensure()
    .max(1000, 'At most 1000 characters')
    .when('decision', {
      is: 'DISPUTE',
      then: (s) => s.required('Say why you dispute it').min(3, 'At least 3 characters'),
    }),
});

export function toAckPayload(v: AckValues): CashAcknowledgementIn {
  const acknowledged = v.decision === 'ACKNOWLEDGE';
  return {
    acknowledged,
    amount_received: acknowledged ? v.amount_received.trim() : null,
    note: orNull(v.note),
  };
}

export type RemitDecision = 'CONFIRM' | 'REJECT' | '';

export interface RemittanceDecisionValues {
  decision: RemitDecision;
  amount_received: string;
  note: string;
}

export const remittanceDecisionSchema: ObjectSchema<RemittanceDecisionValues> = object({
  decision: mixed<RemitDecision>()
    .oneOf(['CONFIRM', 'REJECT'], 'Choose a decision')
    .required('Choose a decision'),
  amount_received: string()
    .trim()
    .ensure()
    .when('decision', {
      is: 'CONFIRM',
      then: () => positiveDecimalField('Amount received'),
    }),
  note: string()
    .trim()
    .ensure()
    .max(1000, 'At most 1000 characters')
    .when('decision', {
      is: 'REJECT',
      then: (s) => s.required('A reason is required to reject').min(3, 'At least 3 characters'),
    }),
});

export function toRemittanceDecisionPayload(v: RemittanceDecisionValues): RemittanceDecisionIn {
  const verified = v.decision === 'CONFIRM';
  return {
    verified,
    note: orNull(v.note),
    ...(verified ? { amount_received: v.amount_received.trim() } : {}),
  };
}

// --- variances --------------------------------------------------------------------------------------------
export interface ResolveVarianceValues {
  outcome: VarianceOutcome | '';
  reason_id: string;
  note: string;
}

export const resolveVarianceSchema: ObjectSchema<ResolveVarianceValues> = object({
  outcome: mixed<VarianceOutcome | ''>()
    .oneOf(['RECOVERED', 'CORRECTED_ERROR', 'WRITTEN_OFF'], 'Choose an outcome')
    .required('Choose an outcome'),
  reason_id: string().ensure(),
  note: reasonField('Explanation'),
});

export function toResolveVariancePayload(v: ResolveVarianceValues): VarianceResolutionIn {
  return {
    outcome: v.outcome as VarianceOutcome,
    note: v.note.trim(),
    reason_id: orNull(v.reason_id),
  };
}

export interface WriteOffValues {
  reason_id: string;
  note: string;
}

export const writeOffSchema: ObjectSchema<WriteOffValues> = object({
  reason_id: string().ensure(),
  note: reasonField('Explanation'),
});

export function toWriteOffPayload(v: WriteOffValues): WriteOffProposalIn {
  return { note: v.note.trim(), reason_id: orNull(v.reason_id) };
}

// --- retention --------------------------------------------------------------------------------------------
export interface RetentionValues {
  staff_member_id: string;
  amount: string;
  currency: string;
  reason_id: string;
  reason: string;
  valid_until: string;
}

export const retentionSchema: ObjectSchema<RetentionValues> = object({
  staff_member_id: string().ensure(),
  amount: positiveDecimalField('Amount to keep'),
  currency: string().ensure(),
  reason_id: string().ensure(),
  reason: reasonField('Why the cash is kept'),
  valid_until: optionalInstant(),
});

export function toRetentionPayload(v: RetentionValues): CashRetentionIn {
  return {
    staff_member_id: orNull(v.staff_member_id),
    amount: v.amount.trim(),
    currency: orNull(v.currency),
    reason_id: orNull(v.reason_id),
    reason: v.reason.trim(),
    valid_until: orNull(v.valid_until),
  };
}

// --- custody adjustment -----------------------------------------------------------------------------------
export interface AdjustmentValues {
  staff_member_id: string;
  kind: CustodyAdjustmentKind;
  amount: string;
  currency: string;
  reason_id: string;
  reason: string;
  reverses_entity_type: ReversibleEntity | '';
  reverses_entity_id: string;
  occurred_at: string;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const adjustmentSchema: ObjectSchema<AdjustmentValues> = object({
  staff_member_id: string().required('Choose the custodian'),
  kind: mixed<CustodyAdjustmentKind>().oneOf(['ADJUSTMENT', 'REVERSAL']).required(),
  amount: signedDecimalField('Amount').test(
    'non-zero',
    'Amount must not be zero',
    (v) => !/^-?\d+(\.\d{1,4})?$/.test(v) || !isZeroDecimal(v.replace(/^-/, '')),
  ),
  currency: string().ensure(),
  reason_id: string().ensure(),
  reason: reasonField('Reason'),
  reverses_entity_type: mixed<ReversibleEntity | ''>()
    .defined()
    .when('kind', {
      is: 'REVERSAL',
      then: (s) => s.test('required', 'Choose the kind of record reversed', (v) => v !== ''),
    }),
  reverses_entity_id: string()
    .trim()
    .ensure()
    .test('uuid', 'Paste the record id (a UUID)', (v) => v === '' || UUID.test(v))
    .when('kind', {
      is: 'REVERSAL',
      then: (s) => s.required('Paste the id of the record reversed'),
    }),
  occurred_at: optionalInstant(),
});

export function toAdjustmentPayload(v: AdjustmentValues): CustodyAdjustmentIn {
  const reverses = v.reverses_entity_type !== '' && v.reverses_entity_id.trim() !== '';
  return {
    staff_member_id: v.staff_member_id,
    kind: v.kind,
    amount: v.amount.trim(),
    currency: orNull(v.currency),
    reason: v.reason.trim(),
    reason_id: orNull(v.reason_id),
    reverses_entity_type: reverses ? (v.reverses_entity_type as ReversibleEntity) : null,
    reverses_entity_id: reverses ? v.reverses_entity_id.trim() : null,
    occurred_at: orNull(v.occurred_at),
  };
}

// --- reasons ----------------------------------------------------------------------------------------------
export interface ReasonValues {
  kind: CashReasonKind;
  label: string;
  description: string;
}

export const reasonSchema: ObjectSchema<ReasonValues> = object({
  kind: mixed<CashReasonKind>()
    .oneOf(['VARIANCE', 'WRITE_OFF', 'RETENTION', 'ADJUSTMENT'])
    .required(),
  label: string()
    .trim()
    .required('Label is required')
    .min(2, 'At least 2 characters')
    .max(120, 'At most 120 characters'),
  description: optionalText('Description', 1000),
});

export function toReasonPayload(v: ReasonValues): CashReasonIn {
  return { kind: v.kind, label: v.label.trim(), description: orNull(v.description) };
}

// --- sync conflict resolution -----------------------------------------------------------------------------
export interface SyncResolutionValues {
  outcome: SyncResolutionOutcome | '';
  reason: string;
  recaptured_entity_type: string;
  recaptured_entity_id: string;
}

export const syncResolutionSchema: ObjectSchema<SyncResolutionValues> = object({
  outcome: mixed<SyncResolutionOutcome | ''>()
    .oneOf(['DISMISSED', 'RECAPTURED'], 'Choose an outcome')
    .required('Choose an outcome'),
  reason: reasonField('Reason'),
  recaptured_entity_type: string()
    .trim()
    .ensure()
    .test('shape', 'Use lower-case letters and underscores (e.g. meter_capture)', (v) =>
      v === '' ? true : /^[a-z_]{1,40}$/.test(v),
    ),
  recaptured_entity_id: string()
    .trim()
    .ensure()
    .test('uuid', 'Paste the record id (a UUID)', (v) => v === '' || UUID.test(v))
    .test('pair', 'Give both the record type and its id, or neither', function pair(v) {
      const t = (this.parent as SyncResolutionValues).recaptured_entity_type.trim();
      return (t === '') === (v === '');
    }),
});

export function toSyncResolutionPayload(v: SyncResolutionValues): SyncResolutionIn {
  const named = v.outcome === 'RECAPTURED' && v.recaptured_entity_id.trim() !== '';
  return {
    outcome: v.outcome as SyncResolutionOutcome,
    reason: v.reason.trim(),
    recaptured_entity_type: named ? v.recaptured_entity_type.trim() : null,
    recaptured_entity_id: named ? v.recaptured_entity_id.trim() : null,
  };
}
