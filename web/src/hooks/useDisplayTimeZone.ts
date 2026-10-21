import { useMemo } from 'react';
import { browserTimeZone } from '../utils/time';

/**
 * IANA zone for displaying instants in the tenant console. `/me` does not expose the tenant's
 * timezone to tenant users yet, so this falls back to the browser zone; when the contract adds it,
 * resolve it here and every tenant view follows.
 */
export function useDisplayTimeZone(): string {
  return useMemo(() => browserTimeZone(), []);
}
