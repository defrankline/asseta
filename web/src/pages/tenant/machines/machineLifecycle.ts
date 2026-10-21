import type { MachineStatus } from '../../../api/types';

export interface MachineStatusAction {
  key: string;
  label: string;
  from: readonly MachineStatus[];
  target: MachineStatus;
  destructive: boolean;
  description: string;
}

/**
 * Service-status changes (ACTIVE ↔ OUT_OF_SERVICE), saved with `PUT /tenant/machines/{id}` (status +
 * `version`). Retiring (DISPOSED) and reinstating use the deactivate / reactivate endpoints.
 */
export const MACHINE_STATUS_ACTIONS: readonly MachineStatusAction[] = [
  {
    key: 'out-of-service',
    label: 'Take out of service',
    from: ['ACTIVE'],
    target: 'OUT_OF_SERVICE',
    destructive: false,
    description:
      'The machine stays in the registry with all of its history but is marked out of service (e.g. under repair). You can return it to service at any time.',
  },
  {
    key: 'return-to-service',
    label: 'Return to service',
    from: ['OUT_OF_SERVICE'],
    target: 'ACTIVE',
    destructive: false,
    description: 'The machine becomes active again and available for jobs.',
  },
];

export const MACHINE_ERROR_HINTS: Readonly<Record<string, string>> = {
  MACHINE_HAS_OPEN_JOBS: 'Complete or cancel the open jobs on this machine first.',
  MACHINE_HAS_OPEN_JOB: 'Complete or cancel the open job on this machine first.',
  MACHINE_HAS_TRACKER: 'Unassign its tracker first (Trackers).',
  MACHINE_ENROLLED: 'End its billable-asset enrollment first.',
  MACHINE_DISPOSED: 'A disposed machine can no longer be changed.',
};

export const RETIRE_CONSEQUENCES =
  'Use this when the machine has been sold, scrapped or returned. It becomes Disposed: its jobs, readings, tracker and staff history are kept, its open staff assignments end, and it can no longer be edited, enrolled or used on new jobs until reinstated.';

/** Edit-form status choices: disposal is a separate, reasoned action. */
export const EDIT_STATUS_OPTIONS = [
  { value: 'ACTIVE', label: 'Active' },
  { value: 'OUT_OF_SERVICE', label: 'Out of service' },
] as const;
