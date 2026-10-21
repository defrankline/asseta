import { useState, type ReactNode } from 'react';
import type { LifecycleReasonIn } from '../../api/lifecycle';
import { DeactivateDialog, ReactivateDialog } from './DeactivateDialog';

export type LifecycleKind = 'deactivate' | 'reactivate';

export interface LifecycleDialogConfig<T> {
  /** Record label for titles, e.g. `C-01 · Acme`. */
  labelOf: (record: T) => string;
  /** Entity noun, e.g. `customer`. */
  noun: string;
  /** Service calls; `body.version` is the version that was read when the record has one. */
  deactivate: (record: T, body: LifecycleReasonIn, idempotencyKey: string) => Promise<T>;
  reactivate: (record: T, body: LifecycleReasonIn, idempotencyKey: string) => Promise<T>;
  /** Called with the saved record after either action. */
  onDone: (record: T, kind: LifecycleKind) => void;
  /** The server answered STALE_VERSION and the user chose Reload. */
  onReload: () => void;
  errorHints?: Readonly<Record<string, string>>;
  /** Domain wording: e.g. `Close` / `Reopen`, `Withdraw` / `Restore`. */
  deactivateLabel?: string;
  reactivateLabel?: string;
  /** What stops working while inactive (shown in the deactivate dialog). */
  consequences?: ReactNode;
}

/**
 * Deactivate / reactivate dialogs for one entity type: `open(kind, record)` shows the dialog,
 * `dialog` renders it (mount it once). Reasons are required; server errors stay in the dialog.
 */
export function useLifecycleDialog<T>(config: LifecycleDialogConfig<T>): {
  open: (kind: LifecycleKind, record: T) => void;
  dialog: ReactNode;
} {
  const [state, setState] = useState<{ kind: LifecycleKind; record: T } | null>(null);
  const close = () => {
    setState(null);
  };
  const reload = () => {
    setState(null);
    config.onReload();
  };
  let dialog: ReactNode = null;
  if (state !== null) {
    const { kind, record } = state;
    const common = {
      entityLabel: config.labelOf(record),
      noun: config.noun,
      onClose: close,
      onReload: reload,
      ...(config.errorHints !== undefined ? { errorHints: config.errorHints } : {}),
    };
    dialog =
      kind === 'deactivate' ? (
        <DeactivateDialog<T>
          {...common}
          {...(config.deactivateLabel !== undefined
            ? { confirmLabel: config.deactivateLabel }
            : {})}
          {...(config.consequences !== undefined ? { consequences: config.consequences } : {})}
          onConfirm={(reason, key) => config.deactivate(record, { reason }, key)}
          onDone={(saved) => {
            config.onDone(saved, 'deactivate');
          }}
        />
      ) : (
        <ReactivateDialog<T>
          {...common}
          {...(config.reactivateLabel !== undefined
            ? { confirmLabel: config.reactivateLabel }
            : {})}
          onConfirm={(reason, key) => config.reactivate(record, { reason }, key)}
          onDone={(saved) => {
            config.onDone(saved, 'reactivate');
          }}
        />
      );
  }
  return {
    open: (kind, record) => {
      setState({ kind, record });
    },
    dialog,
  };
}
