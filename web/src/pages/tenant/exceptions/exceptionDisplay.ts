import type { ExceptionStatus, ExceptionType, ReviewOutcome } from '../../../api/types';
import { EXCEPTION_TYPES, EXCEPTION_STATUSES } from '../../../api/services/meterSchemas';
import type { StatusTone } from '../../../components/display/StatusChip';
import { EXCEPTION_TYPE_LABELS } from '../../../components/meter/exceptionText';
import type { Option } from '../shared/display';

export const EXCEPTION_STATUS_LABELS: Readonly<Record<ExceptionStatus, string>> = {
  OPEN: 'Requires review',
  EXPLAINED: 'Reviewed — explained',
  CONFIRMED: 'Reviewed — discrepancy confirmed',
};
export const EXCEPTION_STATUS_TONES: Readonly<Record<ExceptionStatus, StatusTone>> = {
  OPEN: 'warning',
  EXPLAINED: 'success',
  CONFIRMED: 'info',
};
export const EXCEPTION_STATUS_OPTIONS: readonly Option<ExceptionStatus>[] = EXCEPTION_STATUSES.map(
  (s) => ({ value: s, label: EXCEPTION_STATUS_LABELS[s] }),
);
export const EXCEPTION_TYPE_OPTIONS: readonly Option<ExceptionType>[] = EXCEPTION_TYPES.map(
  (t) => ({
    value: t,
    label: EXCEPTION_TYPE_LABELS[t],
  }),
);

/** Review outcomes, worded neutrally: a review records what was found, not a judgement of a person. */
export const REVIEW_OUTCOME_OPTIONS: readonly Option<ReviewOutcome>[] = [
  { value: 'EXPLAINED', label: 'Explained — a legitimate reason was found' },
  { value: 'CONFIRMED', label: 'Discrepancy confirmed — evidence stands as recorded' },
];
