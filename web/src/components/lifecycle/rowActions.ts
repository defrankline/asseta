import type { ReactNode } from 'react';

/** One command on a record (row menu item or details-page button). Code-defined, never data. */
export interface RowAction {
  key: string;
  label: string;
  onClick: () => void;
  icon?: ReactNode;
  /** Destructive commands (deactivate, retire, cancel) render in the error colour. */
  destructive?: boolean;
  /** Omitted from the menu (e.g. missing permission or not allowed in the current state). */
  hidden?: boolean;
  disabled?: boolean;
  /** Why a disabled command is unavailable (tooltip and helper text on details-page buttons). */
  disabledReason?: string;
}

export interface StandardActionsInput {
  /** Whether the record is currently active (decides Deactivate vs Reactivate). */
  active: boolean;
  onView?: () => void;
  onEdit?: () => void;
  onDeactivate?: () => void;
  onReactivate?: () => void;
  /** May edit (permission and tenant not read-only). Inactive records are not editable. */
  canEdit?: boolean;
  /** May deactivate / reactivate. */
  canChangeState?: boolean;
  viewLabel?: string;
  editLabel?: string;
  deactivateLabel?: string;
  reactivateLabel?: string;
}

/** View / Edit / Deactivate / Reactivate in the standard order, hidden when not applicable. */
export function standardRowActions({
  active,
  onView,
  onEdit,
  onDeactivate,
  onReactivate,
  canEdit = false,
  canChangeState = false,
  viewLabel = 'View details',
  editLabel = 'Edit',
  deactivateLabel = 'Deactivate',
  reactivateLabel = 'Reactivate',
}: StandardActionsInput): RowAction[] {
  const actions: RowAction[] = [];
  if (onView !== undefined) actions.push({ key: 'view', label: viewLabel, onClick: onView });
  if (onEdit !== undefined && canEdit && active) {
    actions.push({ key: 'edit', label: editLabel, onClick: onEdit });
  }
  if (onDeactivate !== undefined && canChangeState && active) {
    actions.push({
      key: 'deactivate',
      label: deactivateLabel,
      onClick: onDeactivate,
      destructive: true,
    });
  }
  if (onReactivate !== undefined && canChangeState && !active) {
    actions.push({ key: 'reactivate', label: reactivateLabel, onClick: onReactivate });
  }
  return actions;
}
