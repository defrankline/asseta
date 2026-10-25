import { Alert, Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import { custodyService } from '../../../../api/services/custodyService';
import type { CashRetentionDto, CustodianDto } from '../../../../api/custodyTypes';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import { recordPath } from '../../../../navigation/recordRoutes';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import { PersonName } from '../../shared/PersonName';
import { DECISION_STATUS_OPTIONS } from './custodyDisplay';
import { RetentionDialog } from './CustodyRequestDialogs';
import { useCashPolicy } from './custodyHooks';
import { CustodianFilter } from './custodyPickers';
import { retentionChip, retentionCustodian, useRetentionActions } from './retentionRecord';

/** Requests to keep field cash instead of remitting it: request, approve / reject (never your own). */
export function RetentionsTab({
  timeZone,
  field = false,
  initialStatus,
}: {
  timeZone: string;
  initialStatus?: string | undefined;
  /** Field work: requests are for the caller's own custody unless office cash permission. */
  field?: boolean;
}) {
  const notify = useNotify();
  const navigate = useNavigate();
  const can = useMutationGuard();
  const policy = useCashPolicy();
  const [status, setStatus] = useState(initialStatus ?? (field ? '' : 'PENDING'));
  const [who, setWho] = useState<CustodianDto | null>(null);
  const [requesting, setRequesting] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<CashRetentionDto>>(
    (query, signal) => custodyService.retentions(query, signal),
    [],
  );
  const canRequest = can(PERMISSIONS.tenantCollectionRecord) || can(PERMISSIONS.tenantFinanceCash);
  const allowed = policy?.retentionAllowed ?? true;
  const reload = () => {
    setReloadKey((k) => k + 1);
  };
  const { actionsFor, dialog } = useRetentionActions(reload);
  const open = (r: CashRetentionDto) => {
    void navigate(recordPath('CASH_RETENTION', r.id));
  };
  const columns: DataColumn<CashRetentionDto>[] = [
    { id: 'at', header: 'Requested', render: (r) => formatInstantIn(r.created_at, timeZone) },
    { id: 'who', header: 'Custodian', render: retentionCustodian },
    { id: 'reason', header: 'Reason', render: (r) => r.reason },
    { id: 'status', header: 'Status', render: retentionChip },
    {
      id: 'until',
      header: 'Valid until',
      render: (r) => (r.valid_until === null ? '—' : formatInstantIn(r.valid_until, timeZone)),
    },
    {
      id: 'by',
      header: 'Requested by',
      render: (r) => <PersonName userId={r.created_by} name={r.created_by_name} />,
    },
    { id: 'note', header: 'Decision note', render: (r) => r.decision_note ?? '—' },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (r) => <MoneyText amount={r.amount} currency={r.currency} />,
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (r) => (
        <RowActionsMenu
          label={`retention of ${retentionCustodian(r)}`}
          actions={[
            {
              key: 'view',
              label: 'View details',
              onClick: () => {
                open(r);
              },
            },
            ...actionsFor(r),
          ]}
        />
      ),
    },
  ];
  return (
    <Box className="flex flex-col gap-3">
      {!allowed && (
        <Alert severity="info">
          Your organisation does not allow keeping cash: everything collected is remitted.
        </Alert>
      )}
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(r) => r.id}
        searchable={false}
        reloadKey={reloadKey}
        filters={{ status: status || undefined, staff_member_id: who?.staff_member_id }}
        emptyTitle="No retention requests"
        isRowMuted={(r) => r.status === 'REJECTED'}
        onRowClick={open}
        toolbar={
          <Box className="flex flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="Status"
              value={status}
              options={DECISION_STATUS_OPTIONS}
              onChange={setStatus}
            />
            <Box sx={{ minWidth: 240 }}>
              <CustodianFilter value={who} onChange={setWho} />
            </Box>
            {canRequest && allowed && (
              <Button
                variant="outlined"
                onClick={() => {
                  setRequesting(true);
                }}
              >
                Request to keep cash
              </Button>
            )}
          </Box>
        }
      />
      {requesting && (
        <RetentionDialog
          ownCustody={
            field &&
            !can(PERMISSIONS.tenantFinanceCash) &&
            policy?.recordersMayRecordForOthers !== true
          }
          timeZone={timeZone}
          onClose={() => {
            setRequesting(false);
          }}
          onRecorded={() => {
            notify.success('Request sent; someone else with the approval permission decides.');
            setReloadKey((k) => k + 1);
          }}
        />
      )}
      {dialog}
    </Box>
  );
}
