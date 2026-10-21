import type { ProvisioningState } from '../../../api/types';
import { STATE_TRANSITIONS } from './trackerForms';

export type TrackerStateActionKey = 'suspend' | 'reactivate' | 'retire';

export interface TrackerStateAction {
  key: TrackerStateActionKey;
  label: string;
  target: ProvisioningState;
}

/** State changes offered as commands (`POST /tenant/trackers/{id}/state`, reason required). */
export const TRACKER_STATE_ACTIONS: readonly TrackerStateAction[] = [
  { key: 'suspend', label: 'Suspend', target: 'SUSPENDED' },
  { key: 'reactivate', label: 'Reactivate', target: 'REGISTERED' },
  { key: 'retire', label: 'Retire (decommission)', target: 'RETIRED' },
];

export function canTransition(from: ProvisioningState, to: ProvisioningState): boolean {
  return STATE_TRANSITIONS[from].includes(to);
}

export const TRACKER_ERROR_HINTS: Readonly<Record<string, string>> = {
  INVALID_STATE_TRANSITION: 'The tracker state has changed; reload to see what is allowed now.',
  TRACKER_RETIRED: 'A retired tracker can no longer be changed.',
  ALREADY_INACTIVE: 'The tracker is already in that state; reload to see it.',
};

export const SUSPEND_DESCRIPTION =
  'While suspended, data from this device is quarantined (tracker inactive) and not used for location, hours or alerts. The assignment is kept. You can reactivate it later.';

export const RETIRE_CONSEQUENCES =
  'Retirement is permanent: the device can no longer be assigned, and anything it sends is quarantined. Its assignment and ingestion history are kept for audit. Unassign it from its machine first if it is still fitted.';
