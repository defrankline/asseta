import type {
  SetupCheckDto,
  SetupStepDto,
  SetupStepKey,
  SetupStepStatus,
} from '../../../api/services/setupChecklistService';
import type { StatusTone } from '../../../components/display/StatusChip';

export const STEP_STATUS_LABELS: Readonly<Record<SetupStepStatus, string>> = {
  DONE: 'Done',
  TODO: 'To do',
  NOT_NEEDED: 'Not needed',
  NOT_APPLICABLE: 'Not used',
};

export const STEP_STATUS_TONES: Readonly<Record<SetupStepStatus, StatusTone>> = {
  DONE: 'success',
  TODO: 'info',
  NOT_NEEDED: 'default',
  NOT_APPLICABLE: 'default',
};

/** What a step's count counts ("3 of 5 machines"); steps without a meaningful unit show "3 of 5". */
const STEP_UNITS: Partial<Record<SetupStepKey, string>> = {
  MACHINE_TYPES_AND_RATES: 'machine types',
  TRACKERS: 'machines',
  REASON_LISTS: 'lists',
  METER_BASELINES: 'machines',
};

const CHECK_UNITS: Readonly<Record<string, string>> = {
  APPROVERS: 'people',
  FIELD_USERS_LINKED: 'logins',
  RATE_CARDS: 'machine types',
  PRIMARY_TRACKER: 'machines',
  ENROLLED: 'machines',
};

function countText(
  done: number | null,
  total: number | null,
  unit: string | undefined,
): string | null {
  // "1 of 1" says nothing a status does not: only real counts are shown.
  if (done === null || total === null || total <= 1) return null;
  return `${String(done)} of ${String(total)}${unit === undefined ? '' : ` ${unit}`}`;
}

export const stepCount = (s: SetupStepDto) =>
  countText(s.done_count, s.total_count, STEP_UNITS[s.key]);
export const checkCount = (c: SetupCheckDto) =>
  countText(c.done_count, c.total_count, CHECK_UNITS[c.key]);

/** Screen names for the "Go to …" buttons, by path (the query string only selects a view). */
const SCREEN_NAMES: Readonly<Record<string, string>> = {
  '/tenant/subscription': 'Subscription and settings',
  '/tenant/access': 'People and access',
  '/tenant/staff': 'Staff',
  '/tenant/machines': 'Machines',
  '/tenant/customers': 'Customers',
  '/tenant/trackers': 'Trackers',
  '/tenant/geofences': 'Sites and geofences',
  '/tenant/policies': 'Policies',
  '/tenant/hours/reasons': 'Customer-hours reasons',
  '/tenant/engine-hour-reasons': 'Engine-hour reasons',
  '/tenant/finance/cash': 'Cash reasons',
  '/tenant/revenue-reasons': 'Revenue reasons',
  '/tenant/finance/deposit-accounts': 'Deposit accounts',
  '/tenant/meter-baselines': 'Meter baselines',
  '/tenant/jobs': 'Jobs',
};

export function screenName(link: string): string | null {
  const path = link.split('?')[0] ?? link;
  return SCREEN_NAMES[path] ?? null;
}

export const goToLabel = (link: string) => {
  const name = screenName(link);
  return name === null ? 'Open this step' : `Go to ${name}`;
};

/** Steps shown on the page (in order) and the ones the company does not use. */
export function splitSteps(steps: readonly SetupStepDto[]) {
  const ordered = [...steps].sort((a, b) => a.order - b.order);
  return {
    shown: ordered.filter((s) => s.status !== 'NOT_APPLICABLE'),
    unused: ordered.filter((s) => s.status === 'NOT_APPLICABLE'),
  };
}

export const SETUP_ERROR_HINTS: Readonly<Record<string, string>> = {
  SETUP_STEP_REQUIRED: 'Every company needs this step, so it cannot be skipped.',
};
