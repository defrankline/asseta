import type { ReactNode } from 'react';
import { LifecycleActionDialog, type LifecycleActionDialogProps } from './LifecycleActionDialog';

type Shared<T> = Omit<
  LifecycleActionDialogProps<T>,
  'title' | 'description' | 'confirmLabel' | 'destructive'
>;

export interface DeactivateDialogProps<T> extends Shared<T> {
  /** Record label, e.g. `EX-01 · Excavator`. */
  entityLabel: string;
  /** Entity noun for the default wording, e.g. `customer` (default `record`). */
  noun?: string;
  /** Extra consequences specific to the entity (what stops working). */
  consequences?: ReactNode;
  title?: string;
  confirmLabel?: string;
  description?: ReactNode;
}

/**
 * "Delete" for records with history: deactivate (or retire / close / cancel) with a required
 * reason. Explains that nothing is erased and the record can be reactivated.
 */
export function DeactivateDialog<T>({
  entityLabel,
  noun = 'record',
  consequences,
  title,
  confirmLabel = 'Deactivate',
  description,
  ...rest
}: DeactivateDialogProps<T>) {
  return (
    <LifecycleActionDialog<T>
      {...rest}
      destructive
      title={title ?? `${confirmLabel} ${entityLabel}`}
      confirmLabel={confirmLabel}
      description={
        description ?? (
          <>
            <p className="m-0">
              The {noun} <strong>{entityLabel}</strong> will be marked inactive. It stays in the
              system with all of its history, is hidden from lists and pickers by default, and
              cannot be used for new work. You can reactivate it later.
            </p>
            {consequences !== undefined && <p className="mb-0 mt-2">{consequences}</p>}
          </>
        )
      }
    />
  );
}

export interface ReactivateDialogProps<T> extends Shared<T> {
  entityLabel: string;
  noun?: string;
  title?: string;
  confirmLabel?: string;
  description?: ReactNode;
}

/** Undo a deactivation; the record becomes available for new work again. */
export function ReactivateDialog<T>({
  entityLabel,
  noun = 'record',
  title,
  confirmLabel = 'Reactivate',
  description,
  ...rest
}: ReactivateDialogProps<T>) {
  return (
    <LifecycleActionDialog<T>
      {...rest}
      title={title ?? `${confirmLabel} ${entityLabel}`}
      confirmLabel={confirmLabel}
      description={
        description ?? (
          <p className="m-0">
            The {noun} <strong>{entityLabel}</strong> will be active again and available for new
            work.
          </p>
        )
      }
    />
  );
}
