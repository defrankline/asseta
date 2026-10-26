import { array, mixed, object, string, type ObjectSchema } from 'yup';
import type { DepositAccountType, RemittanceMethod } from '../../../../api/custodyTypes';
import type {
  AttachmentDto,
  CashFloatIn,
  CashHandoverIn,
  CustodyEntryType,
} from '../../../../api/types';
import { CUSTODY_ENTRY_TYPES, REMITTANCE_METHODS } from '../../../../api/services/financeSchemas';
import { positiveDecimalField } from '../../../platform/shared/validators';
import { optionalText, orNull, requiredInstant } from '../../shared/formRules';

export interface FloatValues {
  staff_member_id: string;
  entry_type: CustodyEntryType;
  amount: string;
  currency: string;
  occurred_at: string;
  reference: string;
  note: string;
}

export const ENTRY_TYPE_OPTIONS: readonly { value: CustodyEntryType; label: string }[] = [
  { value: 'FLOAT_ISSUED', label: 'Float issued' },
  { value: 'OPENING_BALANCE', label: 'Opening balance' },
];

export const floatSchema: ObjectSchema<FloatValues> = object({
  staff_member_id: string().required('Choose the supervisor'),
  entry_type: mixed<CustodyEntryType>().oneOf(CUSTODY_ENTRY_TYPES).required(),
  amount: positiveDecimalField('Amount'),
  currency: string().ensure(),
  occurred_at: requiredInstant('Issued at'),
  reference: optionalText('Reference', 120),
  note: optionalText('Note', 1000),
});

export function toFloatPayload(v: FloatValues): CashFloatIn {
  return {
    staff_member_id: v.staff_member_id,
    entry_type: v.entry_type,
    amount: v.amount.trim(),
    currency: orNull(v.currency),
    occurred_at: v.occurred_at,
    reference: orNull(v.reference),
    note: orNull(v.note),
  };
}

/** Remittance requirements of the CASH_CUSTODY policy in force (all off while the controls are off). */
export interface RemittanceRequirements {
  reference: boolean;
  evidence: boolean;
  account: boolean;
}

export const NO_REMITTANCE_REQUIREMENTS: RemittanceRequirements = {
  reference: false,
  evidence: false,
  account: false,
};

/** Effective CASH_CUSTODY values → what a remittance must carry (the master switch gates them all). */
export function remittanceRequirements(
  values: Readonly<Record<string, unknown>> | null,
): RemittanceRequirements {
  if (values?.enabled !== true) return NO_REMITTANCE_REQUIREMENTS;
  return {
    reference: values.remittance_reference_required === true,
    evidence: values.remittance_evidence_required === true,
    account: values.remittance_account_required === true,
  };
}

export const REMITTANCE_METHOD_OPTIONS: readonly { value: RemittanceMethod; label: string }[] = [
  { value: 'CASH_TO_OFFICE', label: 'Cash handed to the office' },
  { value: 'BANK_DEPOSIT', label: 'Bank deposit' },
  { value: 'MOBILE_MONEY', label: 'Mobile money' },
];

export const REMITTANCE_METHOD_LABELS: Readonly<Record<RemittanceMethod, string>> = {
  CASH_TO_OFFICE: 'Cash handed to the office',
  BANK_DEPOSIT: 'Bank deposit',
  MOBILE_MONEY: 'Mobile money',
};

/** The account type a method pays into (mirrors the backend ACCOUNT_TYPE_METHOD). */
export const METHOD_ACCOUNT_TYPE: Readonly<Record<RemittanceMethod, DepositAccountType>> = {
  CASH_TO_OFFICE: 'CASH_OFFICE',
  BANK_DEPOSIT: 'BANK',
  MOBILE_MONEY: 'MOBILE_MONEY',
};

export const ACCOUNT_TYPE_METHOD: Readonly<Record<DepositAccountType, RemittanceMethod>> = {
  CASH_OFFICE: 'CASH_TO_OFFICE',
  BANK: 'BANK_DEPOSIT',
  MOBILE_MONEY: 'MOBILE_MONEY',
};

/** Bank and mobile-money remittances carry a transaction reference; cash to the office never needs one. */
export const needsReference = (method: RemittanceMethod) => method !== 'CASH_TO_OFFICE';

export const MAX_REMITTANCE_EVIDENCE = 10;

export interface HandoverValues {
  staff_member_id: string;
  amount: string;
  currency: string;
  method: RemittanceMethod;
  deposit_account_id: string;
  reference: string;
  /** Uploaded immediately; only the ids are sent. */
  evidence: AttachmentDto[];
  handed_at: string;
  note: string;
}

/** The tenant's remittance requirements are checked here too, so the form explains them before submit. */
export function handoverSchemaFor(req: RemittanceRequirements): ObjectSchema<HandoverValues> {
  return object({
    staff_member_id: string().ensure(),
    amount: positiveDecimalField('Amount'),
    currency: string().ensure(),
    method: mixed<RemittanceMethod>().oneOf(REMITTANCE_METHODS).required('Choose how it was paid'),
    deposit_account_id: string()
      .ensure()
      .test(
        'account-required',
        'Your organisation requires the company account the money was paid into',
        (v) => !req.account || v !== '',
      ),
    reference: optionalText('Reference', 120).test(
      'reference-required',
      'Your organisation requires the transaction reference for bank and mobile-money remittances',
      function (v) {
        const method = (this.parent as { method: RemittanceMethod }).method;
        return !req.reference || !needsReference(method) || v.trim() !== '';
      },
    ),
    evidence: array(mixed<AttachmentDto>().required())
      .max(MAX_REMITTANCE_EVIDENCE, `At most ${String(MAX_REMITTANCE_EVIDENCE)} photos`)
      .test(
        'evidence-required',
        'Your organisation requires a photo of the deposit slip or payment confirmation',
        (v) => !req.evidence || (v?.length ?? 0) > 0,
      )
      .required(),
    handed_at: requiredInstant('Handed over at'),
    note: optionalText('Note', 1000),
  });
}

export function toHandoverPayload(v: HandoverValues, clientId: string): CashHandoverIn {
  return {
    staff_member_id: orNull(v.staff_member_id),
    amount: v.amount.trim(),
    currency: orNull(v.currency),
    method: v.method,
    deposit_account_id: orNull(v.deposit_account_id),
    handed_at: v.handed_at,
    reference: orNull(v.reference),
    evidence_attachment_ids: v.evidence.map((a) => a.id),
    note: orNull(v.note),
    client_id: clientId,
  };
}
