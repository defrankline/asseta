import { PERMISSIONS } from '../../../access/permissionCodes';
import type { ActivityDto, ActivityType, JobStatus } from '../../../api/types';
import type { PermissionRequirement } from '../../../session/permissions';

/** My jobs sections, in the order a supervisor works them. */
export const FIELD_JOB_SECTIONS: readonly {
  key: string;
  title: string;
  status: JobStatus;
  empty: string;
  /** Closed jobs are a short recent history; open ones are listed in full. */
  pageSize: number;
}[] = [
  {
    key: 'running',
    title: 'In progress',
    status: 'IN_PROGRESS',
    empty: 'No job is running.',
    pageSize: 100,
  },
  {
    key: 'ready',
    title: 'Ready to start',
    status: 'APPROVED',
    empty: 'No approved job is waiting to start.',
    pageSize: 100,
  },
  {
    key: 'closed',
    title: 'Recently closed',
    status: 'COMPLETED',
    empty: 'No completed jobs yet.',
    pageSize: 10,
  },
];

/** The next thing to do on a job, from its status and the evidence already recorded. */
export type FieldStep = 'OPENING' | 'START' | 'CLOSING' | 'ACK' | 'COMPLETE' | 'DONE' | 'WAITING';

export interface FieldStepInput {
  status: JobStatus;
  /** An accepted or provisional opening / closing reading exists (job summary). */
  hasOpening: boolean;
  hasClosing: boolean;
  hasAcknowledgement: boolean;
}

/** Mirrors the server rules: START needs an opening reading; COMPLETE a closing reading and an ack. */
export function nextFieldStep(s: FieldStepInput): FieldStep {
  if (s.status === 'APPROVED') return s.hasOpening ? 'START' : 'OPENING';
  if (s.status === 'IN_PROGRESS') {
    if (!s.hasClosing) return 'CLOSING';
    return s.hasAcknowledgement ? 'COMPLETE' : 'ACK';
  }
  if (s.status === 'COMPLETED' || s.status === 'CANCELLED') return 'DONE';
  return 'WAITING';
}

/** Stepper labels in lifecycle order, with the steps they cover. */
export const FIELD_STEPS: readonly { label: string; steps: readonly FieldStep[] }[] = [
  { label: 'Opening reading', steps: ['OPENING'] },
  { label: 'Start job', steps: ['START'] },
  { label: 'Closing reading', steps: ['CLOSING'] },
  { label: 'Customer acknowledgement', steps: ['ACK'] },
  { label: 'Complete job', steps: ['COMPLETE'] },
];

/** Index of the active stepper step (FIELD_STEPS.length once done, -1 before approval). */
export function activeStepIndex(step: FieldStep): number {
  if (step === 'DONE') return FIELD_STEPS.length;
  return FIELD_STEPS.findIndex((s) => s.steps.includes(step));
}

export interface WorkTotals {
  /** Seconds of closed entries per type. */
  seconds: Readonly<Record<ActivityType, number>>;
  /** Entries without an end time (not counted). */
  open: number;
}

/** Running totals of the work log; open entries are counted separately, never estimated. */
export function workTotals(activities: readonly ActivityDto[]): WorkTotals {
  const seconds: Record<ActivityType, number> = {
    WORK: 0,
    STANDBY: 0,
    DOWNTIME: 0,
    MOBILIZATION: 0,
    NOTE: 0,
  };
  let open = 0;
  for (const a of activities) {
    if (a.ended_at === null) {
      open += 1;
      continue;
    }
    const s = (Date.parse(a.ended_at) - Date.parse(a.started_at)) / 1000;
    if (Number.isFinite(s) && s > 0) seconds[a.activity_type] += s;
  }
  return { seconds, open };
}

/** Holding any of these means office oversight of jobs/finance: such users keep the Dashboard. */
export const OFFICE_PERMISSIONS = [
  PERMISSIONS.tenantJobApprove,
  PERMISSIONS.tenantFinanceRead,
] as const;

/**
 * A field user: may work jobs but has no office oversight. Their console opens on My jobs, and their
 * pickers use the field-scoped lists (own jobs, machines they work on).
 */
export function isFieldUser(
  hasPermission: (p: PermissionRequirement, match?: 'all' | 'any') => boolean,
): boolean {
  return hasPermission(PERMISSIONS.tenantJobLog) && !hasPermission(OFFICE_PERMISSIONS, 'any');
}
