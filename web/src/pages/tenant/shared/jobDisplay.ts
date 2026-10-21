import { PERMISSIONS } from '../../../access/permissionCodes';
import type {
  AcknowledgementMethod,
  ActivityType,
  ContractDto,
  JobAction,
  JobStatus,
  StandbyTreatment,
} from '../../../api/types';
import type { StatusTone } from '../../../components/display/StatusChip';
import type { Option } from './display';

export const JOB_STATUS_OPTIONS: readonly Option<JobStatus>[] = [
  { value: 'DRAFT', label: 'Draft' },
  { value: 'PENDING_APPROVAL', label: 'Pending approval' },
  { value: 'APPROVED', label: 'Approved' },
  { value: 'IN_PROGRESS', label: 'In progress' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'CANCELLED', label: 'Cancelled' },
];
export const JOB_STATUS_TONES: Readonly<Record<JobStatus, StatusTone>> = {
  DRAFT: 'default',
  PENDING_APPROVAL: 'info',
  APPROVED: 'info',
  IN_PROGRESS: 'warning',
  COMPLETED: 'success',
  CANCELLED: 'default',
};

export const STANDBY_OPTIONS: readonly Option<StandbyTreatment>[] = [
  { value: 'EXCLUDED', label: 'Excluded (standby not billed)' },
  { value: 'INCLUDED', label: 'Included (billed at the hourly rate)' },
  { value: 'STANDBY_RATE', label: 'Separate standby rate' },
];

export const ACTIVITY_TYPE_OPTIONS: readonly Option<ActivityType>[] = [
  { value: 'WORK', label: 'Work' },
  { value: 'STANDBY', label: 'Standby' },
  { value: 'DOWNTIME', label: 'Downtime' },
  { value: 'MOBILIZATION', label: 'Mobilization' },
  { value: 'NOTE', label: 'Note' },
];

/** `NEGOTIATED` or `RATE_CARD:<version id>` → readable source. */
export function rateSourceLabel(source: string): string {
  if (source === 'NEGOTIATED') return 'Negotiated rate';
  if (source.startsWith('RATE_CARD:')) {
    return `Tenant rate card (version ${source.slice('RATE_CARD:'.length, 'RATE_CARD:'.length + 8)}…)`;
  }
  return source;
}

export interface TransitionDef {
  action: JobAction;
  label: string;
  from: readonly JobStatus[];
  permission: string;
  reasonRequired: boolean;
  description: string;
}

/** Job lifecycle actions, the statuses they apply to and the permission each needs. */
export const JOB_TRANSITIONS: readonly TransitionDef[] = [
  {
    action: 'SUBMIT',
    label: 'Submit for approval',
    from: ['DRAFT'],
    permission: PERMISSIONS.tenantJobWrite,
    reasonRequired: false,
    description: 'Send the job and its price for owner approval.',
  },
  {
    action: 'APPROVE',
    label: 'Approve',
    from: ['PENDING_APPROVAL'],
    permission: PERMISSIONS.tenantJobApprove,
    reasonRequired: false,
    description:
      'Approve the job and its price snapshot. Approved jobs can take an opening reading.',
  },
  {
    action: 'START',
    label: 'Start job',
    from: ['APPROVED'],
    permission: PERMISSIONS.tenantJobLog,
    reasonRequired: false,
    description: 'Start work. Requires an opening meter reading.',
  },
  {
    action: 'COMPLETE',
    label: 'Complete job',
    from: ['IN_PROGRESS'],
    permission: PERMISSIONS.tenantJobLog,
    reasonRequired: false,
    description: 'Complete work. Requires a closing meter reading and a customer acknowledgement.',
  },
  {
    action: 'CANCEL',
    label: 'Cancel job',
    from: ['DRAFT', 'PENDING_APPROVAL', 'APPROVED'],
    permission: PERMISSIONS.tenantJobApprove,
    reasonRequired: true,
    description: 'Cancel the job. A reason is required and recorded in the audit trail.',
  },
];

/** Stable job error codes with what the user can do about them. */
export const JOB_ERROR_HINTS: Readonly<Record<string, string>> = {
  OPENING_REQUIRED: 'Record the opening meter reading (Readings & evidence) before starting.',
  CLOSING_REQUIRED: 'Record the closing meter reading (Readings & evidence) before completing.',
  ACK_REQUIRED: 'Record the customer acknowledgement before completing.',
  MACHINE_BUSY:
    'This machine already has an approved or running job; complete or cancel that job first.',
  INVALID_JOB_TRANSITION: 'The job status has changed; reload to see what is allowed now.',
  REASON_REQUIRED: 'Enter a reason.',
  CONTRACT_NOT_ACTIVE: 'Choose an active contract.',
  NO_RATE:
    'There is no rate card for this machine category; enter a negotiated hourly rate or add a rate card.',
  JOB_NOT_ACTIVE: 'Work can only be logged on approved, running or completed jobs.',
  READING_NOT_ALLOWED:
    'Opening readings are taken on approved jobs, closing readings on jobs in progress.',
  CAPTURE_ID_CONFLICT:
    'This capture was already recorded with different values; close the dialog and start again.',
};

export const RESET_ERROR_HINTS: Readonly<Record<string, string>> = {
  SEGREGATION_OF_DUTIES:
    'You requested this reset, so you cannot decide it. Another approver must review it.',
  RESET_DECIDED: 'This reset has already been decided.',
};

/** Contract number with the customer reference when present. */
export const contractLabel = (c: ContractDto) =>
  c.reference === null ? c.contract_number : `${c.contract_number} · ${c.reference}`;

export const ACK_METHOD_OPTIONS: readonly Option<AcknowledgementMethod>[] = [
  { value: 'NAME_CONFIRMATION', label: 'Name confirmation' },
  { value: 'SIGNATURE', label: 'Signature image' },
];
