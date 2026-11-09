import { Box, Chip } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { custodyService } from '../../../../api/services/custodyService';
import type {
  CashVarianceDto,
  CustodianDto,
  VarianceAssigneeDto,
} from '../../../../api/custodyTypes';
import { AsyncAutocomplete } from '../../../../components/data/AsyncAutocomplete';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import { recordPath } from '../../../../navigation/recordRoutes';
import { UrlPeriodChip } from '../../shared/UrlPeriodChip';
import { urlPeriod } from '../../shared/urlPeriod';
import { initialFilter } from '../../../../navigation/urlFilters';
import { useSession } from '../../../../session/useSession';
import { formatInstantIn } from '../../../../utils/time';
import {
  VARIANCE_OUTCOME_LABELS,
  VARIANCE_KIND_LABELS,
  VARIANCE_SOURCE_LABELS,
  VARIANCE_SOURCE_OPTIONS,
  VARIANCE_STATUS_OPTIONS,
} from './custodyDisplay';
import { searchVarianceAssignees } from './custodyHooks';
import { CustodianFilter } from './custodyPickers';
import { varianceFigure } from './varianceFigures';
import {
  useVarianceActions,
  varianceAssignee,
  varianceChip,
  varianceCustodian,
} from './varianceRecord';

/** Declared ≠ received differences: resolve, or propose / decide a write-off (never your own). */
export function VariancesTab({
  timeZone,
  initialStatus,
}: {
  timeZone: string;
  initialStatus?: string | undefined;
}) {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const direction = params.get('direction');
  const urlDirection = direction === 'SHORTAGE' || direction === 'OVERAGE' ? direction : undefined;
  const directionLabel = urlDirection === 'SHORTAGE' ? 'Shortages only' : 'Overages only';
  const { dateFrom, dateTo } = urlPeriod(params);
  const openOnly = params.get('open_only') === 'true';
  const fromLink =
    urlDirection !== undefined || openOnly || dateFrom !== undefined || dateTo !== undefined;
  const [status, setStatus] = useState(initialStatus ?? (fromLink ? '' : 'OPEN'));
  const [source, setSource] = useState(() =>
    initialFilter(params, 'source_type', VARIANCE_SOURCE_OPTIONS, ''),
  );
  const [who, setWho] = useState<CustodianDto | null>(null);
  const [assignee, setAssignee] = useState<VarianceAssigneeDto | null>(null);
  const canPickAssignee = useSession().hasPermission(PERMISSIONS.tenantFinanceVariance);
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
    { id: 'kind', header: 'Kind', render: (v) => VARIANCE_KIND_LABELS[v.kind] },
    { id: 'who', header: 'Accountable', render: varianceCustodian },
    { id: 'assignee', header: 'Assigned to', render: varianceAssignee },
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
      render: (v) => varianceFigure(v, 'declared_amount'),
    },
    {
      id: 'received',
      header: 'Received',
      align: 'right',
      render: (v) => varianceFigure(v, 'received_amount'),
    },
    {
      id: 'difference',
      header: 'Difference',
      align: 'right',
      render: (v) => varianceFigure(v, 'amount', true),
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
          direction: urlDirection,
          date_from: dateFrom,
          date_to: dateTo,
          open_only: openOnly ? 'true' : undefined,
          staff_member_id: who?.staff_member_id,
          assignee_user_id: assignee?.user_id,
        }}
        emptyTitle="No variances"
        isRowMuted={(v) => v.status === 'RESOLVED'}
        onRowClick={open}
        toolbar={
          <Box className="flex flex-wrap items-center gap-3">
            {urlDirection !== undefined && (
              <Chip
                size="small"
                label={directionLabel}
                onDelete={() => {
                  const next = new URLSearchParams(params);
                  next.delete('direction');
                  setParams(next, { replace: true });
                }}
              />
            )}
            {openOnly && (
              <Chip
                size="small"
                label="Still open"
                onDelete={() => {
                  const next = new URLSearchParams(params);
                  next.delete('open_only');
                  setParams(next, { replace: true });
                }}
              />
            )}
            <UrlPeriodChip params={params} setParams={setParams} />
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
            {canPickAssignee && (
              <Box sx={{ minWidth: 240 }}>
                <AsyncAutocomplete<VarianceAssigneeDto>
                  label="Assigned to"
                  size="small"
                  placeholder="Anyone"
                  value={assignee}
                  onChange={setAssignee}
                  fetchOptions={searchVarianceAssignees}
                  getOptionLabel={(a) => a.display_name}
                  isOptionEqualToValue={(a, b) => a.user_id === b.user_id}
                />
              </Box>
            )}
          </Box>
        }
      />
      {dialog}
    </Box>
  );
}
