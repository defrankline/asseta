import { createContext } from 'react';
import type { ApiError } from '../api/ApiError';
import type { MeResponse, TenantAccess } from '../api/types';
import type { ConsoleMode, PermissionRequirement } from './permissions';

export type SessionStatus = 'loading' | 'ready' | 'error';

export interface SetModeOptions {
  /**
   * Runs in the same update as the mode change, e.g. `navigate(ROUTES.home)`, so the new console
   * never renders on the previous console's route (whose guard would redirect to 403).
   */
  onSwitched?: () => void;
}

export interface SessionContextValue {
  status: SessionStatus;
  me: MeResponse | null;
  error: ApiError | null;
  mode: ConsoleMode;
  activeTenant: TenantAccess | null;
  /** Permission codes in effect for the current mode. */
  permissions: ReadonlySet<string>;
  canUsePlatform: boolean;
  /** True when the active tenant is READ_ONLY; hide/disable mutating actions. */
  isReadOnly: boolean;
  /**
   * Switch console. Entering a mandated client first forces a token refresh so the mandate's
   * Keycloak group is in the access token; resolves once the mode has changed (or was refused).
   */
  setMode: (mode: ConsoleMode, options?: SetModeOptions) => Promise<void>;
  hasPermission: (required: PermissionRequirement, match?: 'all' | 'any') => boolean;
  /** Re-read /me (e.g. after a mandate changed); refreshes in the background once loaded. */
  reload: () => void;
}

export const SessionContext = createContext<SessionContextValue | null>(null);
