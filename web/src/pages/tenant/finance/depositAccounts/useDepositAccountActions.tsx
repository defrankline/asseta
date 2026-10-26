import { useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useCanMutate } from '../../../../access/useCanMutate';
import type { DepositAccountDto } from '../../../../api/custodyTypes';
import { depositAccountService } from '../../../../api/services/depositAccountService';
import { standardRowActions, type RowAction } from '../../../../components/lifecycle/rowActions';
import { useLifecycleDialog } from '../../../../components/lifecycle/useLifecycleDialog';
import { useNotify } from '../../../../notifications/useNotify';
import { DepositAccountDialog } from './DepositAccountDialog';
import {
  DEPOSIT_ACCOUNT_DEACTIVATE_CONSEQUENCES,
  DEPOSIT_ACCOUNT_ERROR_HINTS,
} from './depositAccountForm';

interface Options {
  onChanged: (account: DepositAccountDto) => void;
  onReload: () => void;
  onView?: (account: DepositAccountDto) => void;
}

/** View / Edit / Deactivate / Reactivate a deposit account, gated by `tenant.finance.accounts.manage`. */
export function useDepositAccountActions({ onChanged, onReload, onView }: Options): {
  actionsFor: (account: DepositAccountDto) => RowAction[];
  dialogs: ReactNode;
} {
  const notify = useNotify();
  const canManage = useCanMutate(PERMISSIONS.tenantFinanceAccountsManage);
  const [editing, setEditing] = useState<DepositAccountDto | null>(null);
  const lifecycle = useLifecycleDialog<DepositAccountDto>({
    labelOf: (a) => a.name,
    noun: 'deposit account',
    deactivate: (a, body, key) =>
      depositAccountService.deactivate(a.id, { ...body, version: a.version }, key),
    reactivate: (a, body, key) =>
      depositAccountService.reactivate(a.id, { ...body, version: a.version }, key),
    errorHints: DEPOSIT_ACCOUNT_ERROR_HINTS,
    consequences: DEPOSIT_ACCOUNT_DEACTIVATE_CONSEQUENCES,
    onReload,
    onDone: (a, kind) => {
      notify.success(`${a.name} ${kind === 'deactivate' ? 'deactivated' : 'reactivated'}.`);
      onChanged(a);
    },
  });
  const actionsFor = (a: DepositAccountDto): RowAction[] =>
    standardRowActions({
      active: a.is_active,
      canEdit: canManage,
      canChangeState: canManage,
      ...(onView !== undefined
        ? {
            onView: () => {
              onView(a);
            },
          }
        : {}),
      onEdit: () => {
        setEditing(a);
      },
      onDeactivate: () => {
        lifecycle.open('deactivate', a);
      },
      onReactivate: () => {
        lifecycle.open('reactivate', a);
      },
    });
  const dialogs = (
    <>
      {lifecycle.dialog}
      {editing !== null && (
        <DepositAccountDialog
          account={editing}
          onClose={() => {
            setEditing(null);
          }}
          onReload={onReload}
          onSaved={(a) => {
            notify.success(`${a.name} updated.`);
            onChanged(a);
          }}
        />
      )}
    </>
  );
  return { actionsFor, dialogs };
}
