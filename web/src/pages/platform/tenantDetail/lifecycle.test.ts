import { describe, expect, it } from 'vitest';
import { allowedLifecycleActions } from './lifecycle';

describe('allowedLifecycleActions (ADR-003)', () => {
  const targets = (s: Parameters<typeof allowedLifecycleActions>[0]) =>
    allowedLifecycleActions(s).map((a) => `${a.label}->${a.to}`);
  it('offers only manual, allowed transitions', () => {
    expect(targets('PENDING_ACTIVATION')).toEqual([
      'Activate->ACTIVE',
      'Cancel subscription->CANCELLED',
    ]);
    expect(targets('ACTIVE')).toEqual(['Suspend->SUSPENDED', 'Cancel subscription->CANCELLED']);
    expect(targets('SUSPENDED')).toEqual(['Reactivate->ACTIVE', 'Cancel subscription->CANCELLED']);
    expect(targets('CANCELLED')).toEqual([]);
    expect(targets('EXPIRED')).toEqual([]);
  });
});
