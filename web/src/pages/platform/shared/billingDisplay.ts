import type {
  Cadence,
  EnrollmentEndReason,
  MidCycleAddPolicy,
  MidCycleRemovePolicy,
  PaymentMethod,
  RoundingMode,
} from '../../../api/types';
import type { StatusTone } from '../../../components/display/StatusChip';
import type { SelectOption } from '../../../components/forms/FormikSelectField';
import { SUPPORTED_CURRENCIES } from '../../../utils/money';

export const SUBSCRIPTION_TONES: Readonly<Record<string, StatusTone>> = {
  DRAFT: 'default',
  PENDING_ACTIVATION: 'info',
  ACTIVE: 'success',
  PAST_DUE: 'warning',
  SUSPENDED: 'error',
  CANCELLED: 'default',
  EXPIRED: 'default',
};
export const ACCESS_TONES: Readonly<Record<string, StatusTone>> = {
  FULL: 'success',
  READ_ONLY: 'warning',
  BLOCKED: 'error',
};
export const TENANT_STATUS_TONES: Readonly<Record<string, StatusTone>> = {
  ONBOARDING: 'info',
  ACTIVE: 'success',
  CLOSED: 'default',
};
export const VERIFICATION_TONES: Readonly<Record<string, StatusTone>> = {
  UNVERIFIED: 'warning',
  VERIFIED: 'success',
  REJECTED: 'error',
};
export const INVOICE_TONES: Readonly<Record<string, StatusTone>> = {
  ISSUED: 'warning',
  PARTIALLY_PAID: 'info',
  PAID: 'success',
  VOIDED: 'default',
};
export const PAYMENT_TONES: Readonly<Record<string, StatusTone>> = {
  RECORDED: 'info',
  VERIFIED: 'success',
  REJECTED: 'error',
};
export const PENDING_CHARGE_TONES: Readonly<Record<string, StatusTone>> = {
  PENDING: 'warning',
  INVOICED: 'success',
  WAIVED: 'default',
};

export const CURRENCY_OPTIONS: readonly SelectOption[] = SUPPORTED_CURRENCIES.map((c) => ({
  value: c,
  label: c,
}));

export const CADENCE_OPTIONS: readonly { value: Cadence; label: string }[] = [
  { value: 'MONTHLY', label: 'Monthly' },
  { value: 'YEARLY', label: 'Yearly' },
];
export const ADD_POLICY_OPTIONS: readonly { value: MidCycleAddPolicy; label: string }[] = [
  { value: 'PRORATE_DAILY', label: 'Prorate daily (default)' },
  { value: 'FULL_PERIOD', label: 'Charge full period' },
  { value: 'NEXT_PERIOD', label: 'Start billing next period' },
];
export const REMOVE_POLICY_OPTIONS: readonly { value: MidCycleRemovePolicy; label: string }[] = [
  { value: 'PRORATE_CREDIT', label: 'Prorated credit (default)' },
  { value: 'NO_CREDIT', label: 'No credit' },
];
export const ROUNDING_OPTIONS: readonly { value: RoundingMode; label: string }[] = [
  { value: 'HALF_UP', label: 'Half up (default)' },
  { value: 'HALF_EVEN', label: "Half even (banker's)" },
];
export const PAYMENT_METHOD_OPTIONS: readonly { value: PaymentMethod; label: string }[] = [
  { value: 'CASH', label: 'Cash' },
  { value: 'BANK_TRANSFER', label: 'Bank transfer' },
  { value: 'MOBILE_MONEY', label: 'Mobile money' },
];
export const END_REASON_OPTIONS: readonly { value: EnrollmentEndReason; label: string }[] = [
  { value: 'REMOVED_FROM_FLEET', label: 'Removed from fleet' },
  { value: 'DISPOSED', label: 'Disposed' },
  { value: 'SUBSCRIPTION_ENDED', label: 'Subscription ended' },
  { value: 'CORRECTION', label: 'Correction' },
];

export function optionLabel(
  options: readonly { value: string; label: string }[],
  value: string,
): string {
  return options.find((o) => o.value === value)?.label ?? value;
}
