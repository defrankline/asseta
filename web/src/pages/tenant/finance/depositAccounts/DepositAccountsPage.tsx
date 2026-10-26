import Add from '@mui/icons-material/Add';
import { Button } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { CanMutate } from '../../../../access/CanMutate';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { inactiveFilter } from '../../../../api/lifecycle';
import type { DepositAccountDto } from '../../../../api/custodyTypes';
import { depositAccountService } from '../../../../api/services/depositAccountService';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../../components/data/useServerPage';
import { PageHeader } from '../../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { ActiveChip } from '../../../../components/lifecycle/ActiveChip';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import { ShowInactiveToggle } from '../../../../components/lifecycle/ShowInactiveToggle';
import { depositAccountDetailPath } from '../../../../navigation/routes';
import { useNotify } from '../../../../notifications/useNotify';
import { DepositAccountDialog } from './DepositAccountDialog';
import { DEPOSIT_ACCOUNT_TYPE_LABELS, DEPOSIT_ACCOUNT_TYPE_OPTIONS } from './depositAccountForm';
import { useDepositAccountActions } from './useDepositAccountActions';

/** Company bank, mobile-money and cash-office accounts remittances are paid into (DEC-031 D1). */
export function DepositAccountsPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const [creating, setCreating] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [type, setType] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  const refresh = () => {
    setReloadKey((k) => k + 1);
  };
  const view = (a: DepositAccountDto) => {
    void navigate(depositAccountDetailPath(a.id));
  };
  const { actionsFor, dialogs } = useDepositAccountActions({
    onChanged: refresh,
    onReload: refresh,
    onView: view,
  });
  const filters = useMemo(
    () => ({ account_type: type || undefined, ...inactiveFilter(showInactive) }),
    [type, showInactive],
  );
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      depositAccountService.list(
        { page: q.page, page_size: q.page_size, q: q.q, filters: q.filters },
        signal,
      ),
    [],
  );
  const columns: DataColumn<DepositAccountDto>[] = [
    { id: 'name', header: 'Name', render: (a) => <strong>{a.name}</strong> },
    { id: 'type', header: 'Type', render: (a) => DEPOSIT_ACCOUNT_TYPE_LABELS[a.account_type] },
    { id: 'institution', header: 'Bank or operator', render: (a) => a.institution ?? '—' },
    { id: 'number', header: 'Account number', render: (a) => a.account_number_masked ?? '—' },
    { id: 'currency', header: 'Currency', render: (a) => a.currency },
    { id: 'active', header: 'State', render: (a) => <ActiveChip active={a.is_active} /> },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (a) => <RowActionsMenu label={a.name} actions={actionsFor(a)} />,
    },
  ];
  return (
    <>
      <PageHeader
        title="Deposit accounts"
        subtitle="Company accounts remittances are paid into; supervisors pick one when they remit"
        actions={
          <CanMutate permission={PERMISSIONS.tenantFinanceAccountsManage}>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setCreating(true);
              }}
            >
              New deposit account
            </Button>
          </CanMutate>
        }
      />
      <ServerDataTable<DepositAccountDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(a) => a.id}
        filters={filters}
        searchPlaceholder="Search name or bank / operator"
        emptyTitle="No deposit accounts"
        reloadKey={reloadKey}
        isRowMuted={(a) => !a.is_active}
        onRowClick={view}
        toolbar={
          <>
            <StaticSelectFilter
              label="Type"
              value={type}
              options={DEPOSIT_ACCOUNT_TYPE_OPTIONS}
              onChange={setType}
              allLabel="All types"
            />
            <ShowInactiveToggle checked={showInactive} onChange={setShowInactive} />
          </>
        }
      />
      {creating && (
        <DepositAccountDialog
          onClose={() => {
            setCreating(false);
          }}
          onSaved={(a) => {
            notify.success(`${a.name} added.`);
            refresh();
          }}
        />
      )}
      {dialogs}
    </>
  );
}
