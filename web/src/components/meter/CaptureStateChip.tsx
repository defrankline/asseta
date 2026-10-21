import type { CaptureState } from '../../api/types';
import { StatusChip, type StatusTone } from '../display/StatusChip';

const TONES: Readonly<Record<CaptureState, StatusTone>> = {
  ACCEPTED: 'success',
  PROVISIONAL: 'warning',
  REJECTED: 'error',
  SUPERSEDED: 'default',
};

const LABELS: Readonly<Record<CaptureState, string>> = {
  ACCEPTED: 'Accepted',
  PROVISIONAL: 'Provisional — requires review',
  REJECTED: 'Rejected',
  SUPERSEDED: 'Superseded',
};

/** Meter capture state as text plus tone. */
export function CaptureStateChip({ state }: { state: CaptureState }) {
  return <StatusChip status={state} tones={TONES} label={LABELS[state]} />;
}
