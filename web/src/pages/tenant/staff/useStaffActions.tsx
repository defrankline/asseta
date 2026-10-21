import { useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { staffService } from '../../../api/services/staffService';
import type { StaffDto } from '../../../api/types';
import { standardRowActions, type RowAction } from '../../../components/lifecycle/rowActions';
import { useLifecycleDialog } from '../../../components/lifecycle/useLifecycleDialog';
import { useNotify } from '../../../notifications/useNotify';
import { EditStaffDialog } from './EditStaffDialog';
import { STAFF_DEACTIVATE_CONSEQUENCES, STAFF_ERROR_HINTS } from './staffForm';

interface UseStaffActionsOptions {
  onChanged: (staff: StaffDto) => void;
  onReload: () => void;
  onView?: (staff: StaffDto) => void;
}

/** View / Edit / Deactivate / Reactivate for a staff member, gated by `tenant.staff.write`. */
export function useStaffActions({ onChanged, onReload, onView }: UseStaffActionsOptions): {
  actionsFor: (staff: StaffDto) => RowAction[];
  dialogs: ReactNode;
} {
  const notify = useNotify();
  const canWrite = useCanMutate(PERMISSIONS.tenantStaffWrite);
  const [editing, setEditing] = useState<StaffDto | null>(null);
  const lifecycle = useLifecycleDialog<StaffDto>({
    labelOf: (s) => s.full_name,
    noun: 'staff member',
    deactivate: (s, body, key) =>
      staffService.deactivate(s.id, { ...body, version: s.version }, key),
    reactivate: (s, body, key) =>
      staffService.reactivate(s.id, { ...body, version: s.version }, key),
    errorHints: STAFF_ERROR_HINTS,
    consequences: STAFF_DEACTIVATE_CONSEQUENCES,
    onReload,
    onDone: (s, kind) => {
      notify.success(`${s.full_name} ${kind === 'deactivate' ? 'deactivated' : 'reactivated'}.`);
      onChanged(s);
    },
  });

  const actionsFor = (s: StaffDto): RowAction[] =>
    standardRowActions({
      active: s.is_active,
      canEdit: canWrite,
      canChangeState: canWrite,
      ...(onView !== undefined
        ? {
            onView: () => {
              onView(s);
            },
          }
        : {}),
      onEdit: () => {
        setEditing(s);
      },
      onDeactivate: () => {
        lifecycle.open('deactivate', s);
      },
      onReactivate: () => {
        lifecycle.open('reactivate', s);
      },
    });

  const dialogs = (
    <>
      {lifecycle.dialog}
      {editing !== null && (
        <EditStaffDialog
          staff={editing}
          onClose={() => {
            setEditing(null);
          }}
          onReload={onReload}
          onSaved={(s) => {
            notify.success(`${s.full_name} updated.`);
            onChanged(s);
          }}
        />
      )}
    </>
  );
  return { actionsFor, dialogs };
}
