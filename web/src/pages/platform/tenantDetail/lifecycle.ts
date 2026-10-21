import type { SubscriptionStatus } from '../../../api/types';

export interface LifecycleAction {
  to: SubscriptionStatus;
  label: string;
}

const ACTIVATE: LifecycleAction = { to: 'ACTIVE', label: 'Activate' };
const REACTIVATE: LifecycleAction = { to: 'ACTIVE', label: 'Reactivate' };
const SUSPEND: LifecycleAction = { to: 'SUSPENDED', label: 'Suspend' };
const CANCEL: LifecycleAction = { to: 'CANCELLED', label: 'Cancel subscription' };

/**
 * Manual lifecycle transitions offered per status (ADR-003 / backend ALLOWED_TRANSITIONS).
 * PAST_DUE and EXPIRED are set automatically by entitlement evaluation, never manually.
 */
export function allowedLifecycleActions(status: SubscriptionStatus): readonly LifecycleAction[] {
  switch (status) {
    case 'DRAFT':
      return [CANCEL];
    case 'PENDING_ACTIVATION':
      return [ACTIVATE, CANCEL];
    case 'ACTIVE':
    case 'PAST_DUE':
      return [SUSPEND, CANCEL];
    case 'SUSPENDED':
      return [REACTIVATE, CANCEL];
    case 'CANCELLED':
    case 'EXPIRED':
      return [];
  }
}
