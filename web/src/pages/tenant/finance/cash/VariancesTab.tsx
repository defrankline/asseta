import { Box } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { custodyService } from '../../../../api/services/custodyService';
import type { CashVarianceDto, CustodianDto } from '../../../../api/custodyTypes';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import { recordPath } from '../../../../navigation/recordRoutes';
import { formatInstantIn } from '../../../../utils/time';
import {
  VARIANCE_OUTCOME_LABELS,
  VARIANCE_SOURCE_LABELS,
  VARIANCE_SOURCE_OPTIONS,
  VARIANCE_STATUS_OPTIONS,
} from './custodyDisplay';
import { CustodianFilter } from './custodyPickers';
import { useVarianceActions, varianceChip, varianceCustodian } from './varianceRecord';

/** Declared ≠ received differences: resolve, or propose / decide a write-off (never your own). */
export function VariancesTab({
  timeZone,
  initialStatus,
}: {
  timeZone: string;
  initialStatus?: string | undefined;
}) {
  const navigate = useNavigate();
  const [status, setStatus] = useState(initialStatus ?? 'OPEN');
  const [source, setSource] = useState('');
  const [who, setWho] = useState<CustodianDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<CashVarianceDto>>(
    (query, signal) => custodyService.variances(query, signal),
    [],
  );
  const { actionsFor, dialog } = useVarianceActions(() => {
    setReloadKey((k) => k + 1);
  });
  const open = (v: CashVarianceDto) => {
    void navigate(recordPath('CASH_VARIANCE', v.id));
  };
  const columns: DataColumn<CashVarianceDto>[] = [
    { id: 'at', header: 'Opened', render: (v) => formatInstantIn(v.opened_at, timeZone) },
    { id: 'source', header: 'From', render: (v) => VARIANCE_SOURCE_LABELS[v.source_type] },
    { id: 'who', header: 'Accountable custodian', render: varianceCustodian },
    { id: 'status', header: 'Status', render: varianceChip },
    {
      id: 'outcome',
      header: 'Outcome',
      render: (v) => (v.outcome === null ? '—' : VARIANCE_OUTCOME_LABELS[v.outcome]),
    },
    {
      id: 'declared',
      header: 'Declared',
      align: 'right',
      render: (v) => <MoneyText amount={v.declared_amount} currency={v.currency} />,
    },
    {
      id: 'received',
      header: 'Received',
      align: 'right',
      render: (v) => <MoneyText amount={v.received_amount} currency={v.currency} />,
    },
    {
      id: 'difference',
      header: 'Difference',
      align: 'right',
      render: (v) => <MoneyText amount={v.amount} currency={v.currency} strong />,
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (v) => (
        <RowActionsMenu
          label={`variance of ${varianceCustodian(v)}`}
          actions={[
            {
              key: 'view',
              label: 'View details',
              onClick: () => {
                open(v);
              },
            },
            ...actionsFor(v),
          ]}
        />
      ),
    },
  ];
  return (
    <Box className="flex flex-col gap-3">
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(v) => v.id}
        searchable={false}
        reloadKey={reloadKey}
        filters={{
          status: status || undefined,
          source_type: source || undefined,
          staff_member_id: who?.staff_member_id,
        }}
        emptyTitle="No variances"
        isRowMuted={(v) => v.status === 'RESOLVED'}
        onRowClick={open}
        toolbar={
          <Box className="flex flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="Status"
              value={status}
              options={VARIANCE_STATUS_OPTIONS}
              onChange={setStatus}
            />
            <StaticSelectFilter
              label="From"
              value={source}
              options={VARIANCE_SOURCE_OPTIONS}
              onChange={setSource}
            />
            <Box sx={{ minWidth: 240 }}>
              <CustodianFilter value={who} onChange={setWho} />
            </Box>
          </Box>
        }
      />
      {dialog}
    </Box>
  );
}
