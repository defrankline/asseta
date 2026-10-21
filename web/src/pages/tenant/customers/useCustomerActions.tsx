import { useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { customerService } from '../../../api/services/customerService';
import type { CustomerDto } from '../../../api/types';
import { standardRowActions, type RowAction } from '../../../components/lifecycle/rowActions';
import { useLifecycleDialog } from '../../../components/lifecycle/useLifecycleDialog';
import { useNotify } from '../../../notifications/useNotify';
import { CUSTOMER_DEACTIVATE_CONSEQUENCES, CUSTOMER_ERROR_HINTS } from './customerLifecycle';
import { EditCustomerDialog } from './EditCustomerDialog';

export const customerLabel = (c: CustomerDto) => `${c.code} · ${c.name}`;

interface UseCustomerActionsOptions {
  /** A customer was saved (edit, deactivate, reactivate). */
  onChanged: (customer: CustomerDto) => void;
  /** STALE_VERSION: reload the latest record(s). */
  onReload: () => void;
  onView?: (customer: CustomerDto) => void;
}

/** View / Edit / Deactivate / Reactivate for customers (list rows and the details page). */
export function useCustomerActions({ onChanged, onReload, onView }: UseCustomerActionsOptions): {
  actionsFor: (customer: CustomerDto) => RowAction[];
  dialogs: ReactNode;
} {
  const notify = useNotify();
  const canWrite = useCanMutate(PERMISSIONS.tenantCustomerWrite);
  const [editing, setEditing] = useState<CustomerDto | null>(null);
  const lifecycle = useLifecycleDialog<CustomerDto>({
    labelOf: customerLabel,
    noun: 'customer',
    errorHints: CUSTOMER_ERROR_HINTS,
    consequences: CUSTOMER_DEACTIVATE_CONSEQUENCES,
    deactivate: (c, body, key) =>
      customerService.deactivate(c.id, { ...body, version: c.version }, key),
    reactivate: (c, body, key) =>
      customerService.reactivate(c.id, { ...body, version: c.version }, key),
    onDone: (c, kind) => {
      notify.success(
        `Customer ${c.name} ${kind === 'deactivate' ? 'deactivated' : 'reactivated'}.`,
      );
      onChanged(c);
    },
    onReload,
  });

  const actionsFor = (c: CustomerDto): RowAction[] =>
    standardRowActions({
      active: c.is_active,
      canEdit: canWrite,
      canChangeState: canWrite,
      ...(onView !== undefined
        ? {
            onView: () => {
              onView(c);
            },
          }
        : {}),
      onEdit: () => {
        setEditing(c);
      },
      onDeactivate: () => {
        lifecycle.open('deactivate', c);
      },
      onReactivate: () => {
        lifecycle.open('reactivate', c);
      },
    });

  const dialogs = (
    <>
      {lifecycle.dialog}
      {editing !== null && (
        <EditCustomerDialog
          customer={editing}
          onClose={() => {
            setEditing(null);
          }}
          onReload={onReload}
          onSaved={(c) => {
            notify.success(`Customer ${c.name} updated.`);
            onChanged(c);
          }}
        />
      )}
    </>
  );
  return { actionsFor, dialogs };
}
