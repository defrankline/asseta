import type { EntityChange } from './protocol';

/**
 * Entity kinds announced by `entity.changed` (backend `notification/rules.py` ENTITY_CHANGES).
 * A live-refresh key is either a kind (`alert`: any alert) or `kind:id` (one record).
 */
export const ENTITY = {
  alert: 'alert',
  fleetPosition: 'fleet.position',
  approval: 'approval',
  expense: 'expense',
  customerPayment: 'customer_payment',
  cashHandover: 'cash_handover',
  hireInvoice: 'hire_invoice',
  meterCapture: 'meter_capture',
  meterException: 'meter_exception',
  job: 'job',
  platformInvoice: 'platform_invoice',
  platformPayment: 'platform_payment',
  subscription: 'subscription',
  /** Investigation case opened, escalated, assigned, noted, resolved or reopened. */
  anomalyCase: 'case',
} as const;

export type EntityKind = (typeof ENTITY)[keyof typeof ENTITY];

/** Live-refresh key for one record, e.g. `entityKey(ENTITY.platformInvoice, id)`. */
export function entityKey(entity: string, id?: string | null): string {
  return id === undefined || id === null ? entity : `${entity}:${id}`;
}

/** Whether a change concerns any of the keys. */
export function matchesEntityKeys(change: EntityChange, keys: readonly string[]): boolean {
  return keys.some((key) => {
    const sep = key.indexOf(':');
    if (sep < 0) return key === change.entity;
    return key.slice(0, sep) === change.entity && key.slice(sep + 1) === change.id;
  });
}
