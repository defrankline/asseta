import { useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import type { MachineDto } from '../../../api/types';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { useLifecycleDialog } from '../../../components/lifecycle/useLifecycleDialog';
import { machineService } from '../../../api/services/machineService';
import { useNotify } from '../../../notifications/useNotify';
import { formatMoney } from '../../../utils/money';
import { labelOf, MACHINE_STATUS_OPTIONS, machineLabel } from '../shared/display';
import { EditMachineDialog } from './EditMachineDialog';
import { EnrollMachineDialog } from './EnrollMachineDialog';
import {
  MACHINE_ERROR_HINTS,
  MACHINE_STATUS_ACTIONS,
  RETIRE_CONSEQUENCES,
  type MachineStatusAction,
} from './machineLifecycle';
import { MachineStatusDialog } from './MachineStatusDialog';

type OpenDialog =
  | { kind: 'edit'; machine: MachineDto }
  | { kind: 'enroll'; machine: MachineDto }
  | { kind: 'status'; machine: MachineDto; action: MachineStatusAction }
  | null;

interface UseMachineActionsOptions {
  /** A machine was saved (edit or status change); refresh what shows it. */
  onChanged: (machine: MachineDto) => void;
  /** The server reported STALE_VERSION and the user asked to reload. */
  onReload: () => void;
  /** Adds "View details" (list rows). */
  onView?: (machine: MachineDto) => void;
}

/**
 * Record commands for a machine (view, edit, enroll, status changes), gated by permission and
 * tenant access, plus the dialogs they open. Shared by the list rows and the details page.
 */
export function useMachineActions({ onChanged, onReload, onView }: UseMachineActionsOptions): {
  actionsFor: (machine: MachineDto) => RowAction[];
  dialogs: ReactNode;
} {
  const notify = useNotify();
  const canWrite = useCanMutate(PERMISSIONS.tenantMachineWrite);
  const canEnroll = useCanMutate(PERMISSIONS.tenantBillingEnroll);
  const [open, setOpen] = useState<OpenDialog>(null);
  const close = () => {
    setOpen(null);
  };
  const lifecycle = useLifecycleDialog<MachineDto>({
    labelOf: machineLabel,
    noun: 'machine',
    deactivateLabel: 'Retire',
    reactivateLabel: 'Reinstate',
    consequences: RETIRE_CONSEQUENCES,
    errorHints: MACHINE_ERROR_HINTS,
    deactivate: (m, body, key) =>
      machineService.deactivate(m.id, { ...body, version: m.version }, key),
    reactivate: (m, body, key) =>
      machineService.reactivate(m.id, { ...body, version: m.version }, key),
    onReload,
    onDone: (m, kind) => {
      notify.success(
        kind === 'deactivate' ? `${machineLabel(m)} retired.` : `${machineLabel(m)} reinstated.`,
      );
      onChanged(m);
    },
  });

  const actionsFor = (m: MachineDto): RowAction[] => {
    const disposed = m.status === 'DISPOSED';
    return [
      ...(onView !== undefined
        ? [
            {
              key: 'view',
              label: 'View details',
              onClick: () => {
                onView(m);
              },
            },
          ]
        : []),
      {
        key: 'edit',
        label: 'Edit',
        hidden: !canWrite || disposed,
        onClick: () => {
          setOpen({ kind: 'edit', machine: m });
        },
      },
      {
        key: 'enroll',
        label: 'Enroll as billable asset',
        hidden: !canEnroll || disposed,
        onClick: () => {
          setOpen({ kind: 'enroll', machine: m });
        },
      },
      ...MACHINE_STATUS_ACTIONS.map((a) => ({
        key: a.key,
        label: a.label,
        destructive: a.destructive,
        hidden: !canWrite || !a.from.includes(m.status),
        onClick: () => {
          setOpen({ kind: 'status', machine: m, action: a });
        },
      })),
      {
        key: 'retire',
        label: 'Retire (dispose)',
        destructive: true,
        hidden: !canWrite || disposed,
        onClick: () => {
          lifecycle.open('deactivate', m);
        },
      },
      {
        key: 'reinstate',
        label: 'Reinstate',
        hidden: !canWrite || !disposed,
        onClick: () => {
          lifecycle.open('reactivate', m);
        },
      },
    ];
  };

  const reload = () => {
    close();
    onReload();
  };

  let dialogs: ReactNode = null;
  if (open?.kind === 'edit') {
    dialogs = (
      <EditMachineDialog
        machine={open.machine}
        onClose={close}
        onSaved={(saved) => {
          notify.success(`Machine ${saved.asset_code} updated.`);
          onChanged(saved);
        }}
        onReloadRequested={reload}
      />
    );
  } else if (open?.kind === 'status') {
    dialogs = (
      <MachineStatusDialog
        machine={open.machine}
        action={open.action}
        onClose={close}
        onReload={reload}
        onDone={(saved) => {
          notify.success(
            `${machineLabel(saved)} is now ${labelOf(MACHINE_STATUS_OPTIONS, saved.status).toLowerCase()}.`,
          );
          onChanged(saved);
        }}
      />
    );
  } else if (open?.kind === 'enroll') {
    dialogs = (
      <EnrollMachineDialog
        machine={open.machine}
        onClose={close}
        onEnrolled={(r) => {
          notify.success(
            r.charge === null
              ? `${r.enrollment.asset_label} enrolled as a billable asset.`
              : `${r.enrollment.asset_label} enrolled; pending ${formatMoney(r.charge.amount, r.charge.currency)} recorded.`,
          );
        }}
      />
    );
  }
  return {
    actionsFor,
    dialogs: (
      <>
        {dialogs}
        {lifecycle.dialog}
      </>
    ),
  };
}
