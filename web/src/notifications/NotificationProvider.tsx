import { Alert, Button, Snackbar } from '@mui/material';
import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { ApiError } from '../api/ApiError';
import { newUuid } from '../api/ids';
import {
  NotificationContext,
  type NotificationSeverity,
  type Notifier,
  type ToastAction,
  type ToastOptions,
} from './NotificationContext';

interface Toast {
  id: string;
  message: string;
  severity: NotificationSeverity;
  action: ToastAction | null;
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.correlationId !== null
      ? `${error.message} (ref ${error.correlationId})`
      : error.message;
  }
  return error instanceof Error && error.message !== '' ? error.message : fallback;
}

/** Queue-based toast provider: one Snackbar at a time, in arrival order. */
export function NotificationProvider({ children }: { children: ReactNode }) {
  const [queue, setQueue] = useState<Toast[]>([]);
  const current = queue[0];

  const notify = useCallback(
    (message: string, severity: NotificationSeverity = 'info', options?: ToastOptions) => {
      setQueue((q) => [
        ...q,
        { id: newUuid(), message, severity, action: options?.action ?? null },
      ]);
    },
    [],
  );

  const dismiss = useCallback(() => {
    setQueue((q) => q.slice(1));
  }, []);

  const value = useMemo<Notifier>(
    () => ({
      notify,
      success: (m) => {
        notify(m, 'success');
      },
      info: (m) => {
        notify(m, 'info');
      },
      warning: (m) => {
        notify(m, 'warning');
      },
      error: (e, fallback = 'Something went wrong.') => {
        notify(errorMessage(e, fallback), 'error');
      },
    }),
    [notify],
  );

  return (
    <NotificationContext.Provider value={value}>
      {children}
      <Snackbar
        key={current?.id}
        open={current !== undefined}
        autoHideDuration={current?.severity === 'error' ? 8000 : 4000}
        onClose={(_e, reason) => {
          if (reason !== 'clickaway') dismiss();
        }}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        {current !== undefined ? (
          <Alert
            variant="filled"
            severity={current.severity}
            onClose={dismiss}
            action={
              current.action !== null ? (
                <>
                  <Button
                    color="inherit"
                    size="small"
                    onClick={() => {
                      current.action?.onClick();
                      dismiss();
                    }}
                  >
                    {current.action.label}
                  </Button>
                  <Button color="inherit" size="small" aria-label="Dismiss" onClick={dismiss}>
                    ✕
                  </Button>
                </>
              ) : undefined
            }
          >
            {current.message}
          </Alert>
        ) : undefined}
      </Snackbar>
    </NotificationContext.Provider>
  );
}
