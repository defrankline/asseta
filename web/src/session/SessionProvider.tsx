import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { toApiError, type ApiError } from '../api/ApiError';
import { registerRequestContext } from '../api/requestContext';
import { meService } from '../api/services/meService';
import type { MeResponse } from '../api/types';
import { loadStoredMode, storeMode } from './modeStorage';
import {
  canUsePlatformConsole,
  effectivePermissions,
  findTenant,
  isGranted,
  isModeAllowed,
  NO_MODE,
  resolveInitialMode,
  type ConsoleMode,
} from './permissions';
import { SessionContext, type SessionContextValue, type SessionStatus } from './SessionContext';

interface SessionProviderProps {
  children: ReactNode;
  /** Injectable loader for tests. */
  loadMe?: (signal: AbortSignal) => Promise<MeResponse>;
}

/** Loads GET /me once authenticated and exposes mode, tenant and permission state. */
const defaultLoadMe = (signal: AbortSignal) => meService.getMe(signal);

interface LoadResult {
  key: number;
  me: MeResponse | null;
  error: ApiError | null;
}

export function SessionProvider({ children, loadMe = defaultLoadMe }: SessionProviderProps) {
  const [result, setResult] = useState<LoadResult>({ key: -1, me: null, error: null });
  const [mode, setModeState] = useState<ConsoleMode>(NO_MODE);
  const [reloadKey, setReloadKey] = useState(0);
  const { me, error } = result;
  const status: SessionStatus =
    result.key !== reloadKey ? 'loading' : error !== null ? 'error' : 'ready';

  useEffect(() => {
    const controller = new AbortController();
    loadMe(controller.signal)
      .then((data) => {
        setModeState(resolveInitialMode(data, loadStoredMode()));
        setResult({ key: reloadKey, me: data, error: null });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setResult({ key: reloadKey, me: null, error: toApiError(err) });
      });
    return () => {
      controller.abort();
    };
  }, [loadMe, reloadKey]);

  const activeTenantId = mode.kind === 'tenant' ? mode.tenantId : null;
  useEffect(
    () => registerRequestContext({ getActiveTenantId: () => activeTenantId }),
    [activeTenantId],
  );

  const setMode = useCallback(
    (next: ConsoleMode) => {
      if (!isModeAllowed(me, next)) return;
      storeMode(next);
      setModeState(next);
    },
    [me],
  );

  const reload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);

  const value = useMemo<SessionContextValue>(() => {
    const permissions = effectivePermissions(me, mode);
    const activeTenant = activeTenantId === null ? null : findTenant(me, activeTenantId);
    return {
      status,
      me,
      error,
      mode,
      activeTenant,
      permissions,
      canUsePlatform: canUsePlatformConsole(me),
      isReadOnly: activeTenant?.access_state === 'READ_ONLY',
      setMode,
      hasPermission: (required, match) => isGranted(permissions, required, match),
      reload,
    };
  }, [status, me, error, mode, activeTenantId, setMode, reload]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
