import { useSession } from '../session/useSession';

/**
 * Tenant capabilities a policy can switch off (`/me` tenants[].disabled_capabilities). Menus for a
 * disabled capability are already omitted by the server; these gate everything else on the web.
 */
export const CAPABILITY = {
  customerHours: 'CUSTOMER_HOURS',
} as const;

export type CapabilityCode = (typeof CAPABILITY)[keyof typeof CAPABILITY];

/** False when the active tenant's effective policy switches the capability off. */
export function useCapabilityEnabled(capability: CapabilityCode): boolean {
  const { activeTenant } = useSession();
  return !(activeTenant?.disabled_capabilities ?? []).includes(capability);
}
