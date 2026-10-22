import Add from '@mui/icons-material/Add';
import { Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { useSearchParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { CanMutate } from '../../../access/CanMutate';
import { expenseService } from '../../../api/services/expenseService';
import type { ExpenseDto, MachineDto, StaffDto } from '../../../api/types';
import { ExportMenu } from '../../../components/data/ExportMenu';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import { initialFilter } from '../../../navigation/urlFilters';
import type { FetchPage } from '../../../components/data/useServerPage';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { labelOf } from '../shared/display';
import {
  EXPENSE_STATUS_OPTIONS,
  EXPENSE_STATUS_TONES,
  PAID_FROM_LABELS,
} from '../shared/financeDisplay';
import { MachineFilter, StaffFilter } from '../shared/financePickers';
import { useExpenseCategoryLabels } from '../shared/useFinanceLabels';
import { useMachineLabels } from '../shared/useMachineLabels';
import { ExpenseDetailsDrawer } from './ExpenseDetailsDrawer';
import { RecordExpenseDialog } from './RecordExpenseDialog';
import { ENTITY } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';

/** Field expenses: list with filters, details (receipts, GPS, policy, approval), console capture. */
export function ExpensesTab({ timeZone }: { timeZone: string }) {
  const notify = useNotify();
  const categoryLabel = useExpenseCategoryLabels();
  const machineLabel = useMachineLabels();
  const [params] = useSearchParams();
  const [status, setStatus] = useState(() =>
    initialFilter(params, 'status', EXPENSE_STATUS_OPTIONS, ''),
  );
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [custodian, setCustodian] = useState<StaffDto | null>(null);
  const [viewing, setViewing] = useState<ExpenseDto | null>(null);
  const [recording, setRecording] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const liveReload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  useLiveRefresh([ENTITY.expense, ENTITY.approval], liveReload);
  const fetchPage = useCallback<FetchPage<ExpenseDto>>(
    (query, signal) => expenseService.list(query, signal),
    [],
  );
  const columns: DataColumn<ExpenseDto>[] = [
    { id: 'at', header: 'Incurred', render: (e) => formatInstantIn(e.incurred_at, timeZone) },
    { id: 'desc', header: 'Description', render: (e) => e.description },
    { id: 'cat', header: 'Category', render: (e) => categoryLabel(e.category_id) },
    {
      id: 'attr',
      header: 'Machine',
      render: (e) => (e.machine_id === null ? 'Unattributed' : machineLabel(e.machine_id)),
    },
    { id: 'paid', header: 'Paid from', render: (e) => PAID_FROM_LABELS[e.paid_from] },
    {
      id: 'status',
      header: 'Status',
      render: (e) => (
        <StatusChip
          status={e.status}
          tones={EXPENSE_STATUS_TONES}
          label={labelOf(EXPENSE_STATUS_OPTIONS, e.status)}
        />
      ),
    },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (e) => <MoneyText amount={e.amount} currency={e.currency} />,
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (e) => (
        <RowActionsMenu
          label={`expense ${e.description}`}
          actions={[
            {
              key: 'view',
              label: 'View details',
              onClick: () => {
                setViewing(e);
              },
            },
          ]}
        />
      ),
    },
  ];
  return (
    <>
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(e) => e.id}
        searchable={false}
        reloadKey={reloadKey}
        filters={{
          status: status || undefined,
          machine_id: machine?.id,
          custodian_staff_id: custodian?.id,
        }}
        emptyTitle="No expenses"
        isRowMuted={(e) => e.status === 'REJECTED'}
        onRowClick={setViewing}
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="Status"
              value={status}
              options={EXPENSE_STATUS_OPTIONS}
              onChange={setStatus}
            />
            <Box sx={{ minWidth: 220 }}>
              <MachineFilter label="Machine" value={machine} onChange={setMachine} />
            </Box>
            <Box sx={{ minWidth: 220 }}>
              <StaffFilter
                label="Custodian"
                supervisorsOnly
                value={custodian}
                onChange={setCustodian}
              />
            </Box>
            <Box className="flex-1" />
            <ExportMenu
              reports={[
                {
                  code: 'expenses',
                  filters: {
                    status,
                    machine_id: machine?.id,
                    custodian_staff_id: custodian?.id,
                  },
                },
              ]}
            />
            <CanMutate permission={PERMISSIONS.tenantExpenseWrite}>
              <Button
                variant="contained"
                startIcon={<Add />}
                onClick={() => {
                  setRecording(true);
                }}
              >
                Record expense
              </Button>
            </CanMutate>
          </Box>
        }
      />
      {viewing !== null && (
        <ExpenseDetailsDrawer
          expense={viewing}
          timeZone={timeZone}
          onClose={() => {
            setViewing(null);
          }}
        />
      )}
      {recording && (
        <RecordExpenseDialog
          timeZone={timeZone}
          onClose={() => {
            setRecording(false);
          }}
          onRecorded={(e) => {
            notify.success(
              e.status === 'APPROVED'
                ? 'Expense recorded and auto-approved under the policy limit.'
                : 'Expense recorded; it is waiting for approval.',
            );
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
