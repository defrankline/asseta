import {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { toApiError, type ApiError } from '../api/ApiError';
import { registerRequestContext, requestContext } from '../api/requestContext';
import { meService } from '../api/services/meService';
import type { MeResponse } from '../api/types';
import { NotificationContext } from '../notifications/NotificationContext';
import { mandateLostMessage } from './mandateDisplay';
import { loadStoredMode, storeMode } from './modeStorage';
import {
  canUsePlatformConsole,
  effectivePermissions,
  findTenant,
  isGranted,
  isMandated,
  isModeAllowed,
  NO_MODE,
  resolveInitialMode,
  type ConsoleMode,
} from './permissions';
import { SessionContext, type SessionContextValue, type SessionStatus } from './SessionContext';

const PLATFORM_MODE: ConsoleMode = { kind: 'platform' };

interface SessionProviderProps {
  children: ReactNode;
  /** Injectable loader for tests. */
  loadMe?: (signal: AbortSignal) => Promise<MeResponse>;
  /**
   * Called after the session returned to the platform context because a mandate ended
   * (e.g. to navigate away from the client's pages).
   */
  onMandateLost?: () => void;
}

/** Loads GET /me once authenticated and exposes mode, tenant and permission state. */
const defaultLoadMe = (signal: AbortSignal) => meService.getMe(signal);

interface LoadResult {
  key: number;
  me: MeResponse | null;
  error: ApiError | null;
}

export function SessionProvider({
  children,
  loadMe = defaultLoadMe,
  onMandateLost,
}: SessionProviderProps) {
  const notifier = useContext(NotificationContext);
  const [result, setResult] = useState<LoadResult>({ key: -1, me: null, error: null });
  const [mode, setModeState] = useState<ConsoleMode>(NO_MODE);
  const [reloadKey, setReloadKey] = useState(0);
  const { me, error } = result;
  const status: SessionStatus =
    result.key !== reloadKey ? 'loading' : error !== null ? 'error' : 'ready';

  // Latest values for the framework-agnostic request-context callbacks.
  const latest = useRef({ me, mode, notifier, onMandateLost });
  useEffect(() => {
    latest.current = { me, mode, notifier, onMandateLost };
  });
  /** One mandate-loss reaction per load of /me (parallel requests fail together). */
  const handlingLoss = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    loadMe(controller.signal)
      .then((data) => {
        handlingLoss.current = false;
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

  const reload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);

  useEffect(
    () =>
      registerRequestContext({
        onMandateLost: (tenantId) => {
          const current = latest.current;
          if (handlingLoss.current || !canUsePlatformConsole(current.me)) return;
          handlingLoss.current = true;
          const lostId =
            tenantId ?? (current.mode.kind === 'tenant' ? current.mode.tenantId : null);
          const client = lostId === null ? null : findTenant(current.me, lostId);
          storeMode(PLATFORM_MODE);
          setModeState(PLATFORM_MODE);
          current.notifier?.warning(mandateLostMessage(client?.name ?? null));
          current.onMandateLost?.();
          reload();
        },
      }),
    [reload],
  );

  const setMode = useCallback(
    async (next: ConsoleMode) => {
      if (!isModeAllowed(me, next)) return;
      if (next.kind === 'tenant' && isMandated(findTenant(me, next.tenantId))) {
        // The API honours a mandate group only when it is in the token: refresh before entering.
        try {
          await requestContext.refreshAccessToken();
        } catch (err) {
          latest.current.notifier?.error(err, 'Could not refresh your session.');
          return;
        }
      }
      storeMode(next);
      setModeState(next);
    },
    [me],
  );

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
