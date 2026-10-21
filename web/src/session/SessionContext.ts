import { createContext } from 'react';
import type { ApiError } from '../api/ApiError';
import type { MeResponse, TenantAccess } from '../api/types';
import type { ConsoleMode, PermissionRequirement } from './permissions';

export type SessionStatus = 'loading' | 'ready' | 'error';

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
  setMode: (mode: ConsoleMode) => void;
  hasPermission: (required: PermissionRequirement, match?: 'all' | 'any') => boolean;
  reload: () => void;
}

export const SessionContext = createContext<SessionContextValue | null>(null);
