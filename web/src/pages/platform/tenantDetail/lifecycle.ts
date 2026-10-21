import type { SubscriptionStatus } from '../../../api/types';
import type { SelectOption } from '../../../components/forms/FormikSelectField';

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

const optionsFor = (status: SubscriptionStatus): readonly SelectOption[] =>
  allowedLifecycleActions(status).map((a) => ({ value: a.to, label: a.label }));

/** Static select options per current status (the manual transitions above). */
export const LIFECYCLE_ACTION_OPTIONS: Readonly<
  Record<SubscriptionStatus, readonly SelectOption[]>
> = {
  DRAFT: optionsFor('DRAFT'),
  PENDING_ACTIVATION: optionsFor('PENDING_ACTIVATION'),
  ACTIVE: optionsFor('ACTIVE'),
  PAST_DUE: optionsFor('PAST_DUE'),
  SUSPENDED: optionsFor('SUSPENDED'),
  CANCELLED: optionsFor('CANCELLED'),
  EXPIRED: optionsFor('EXPIRED'),
};
