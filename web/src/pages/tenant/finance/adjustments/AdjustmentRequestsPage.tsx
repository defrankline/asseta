import { Box, Button, Tooltip } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useNavigate, useSearchParams } from 'react-router';
import type { AdjustmentRequestDto } from '../../../../api/adjustmentTypes';
import { adjustmentService } from '../../../../api/services/adjustmentService';
import type { CustomerDto, MachineDto } from '../../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { PageHeader } from '../../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { ADJUSTMENT_ROUTES, adjustmentRequestPath } from '../../../../navigation/adjustmentRoutes';
import { initialFilter } from '../../../../navigation/urlFilters';
import { formatInstantIn } from '../../../../utils/time';
import { hoursText, OWN_REQUEST_TEXT } from '../../hours/hoursDisplay';
import { CustomerFilter, MachineFilter } from '../../shared/financePickers';
import { PersonName } from '../../shared/PersonName';
import {
  REQUEST_STATUS_LABELS,
  REQUEST_STATUS_OPTIONS,
  REQUEST_STATUS_TONES,
  REQUEST_TYPE_LABELS,
  REQUEST_TYPE_OPTIONS,
} from './adjustmentDisplay';
import { useAdjustmentRequestActions } from './useAdjustmentRequestActions';

/** Corrections, refunds, reversals and voids: proposed by one person, decided by another. */
export function AdjustmentRequestsPage() {
  const navigate = useNavigate();
  const timeZone = useDisplayTimeZone();
  const [params] = useSearchParams();
  const originalId = params.get('original_id') ?? undefined;
  const [status, setStatus] = useState(() =>
    initialFilter(
      params,
      'status',
      REQUEST_STATUS_OPTIONS,
      originalId === undefined ? 'PROPOSED' : '',
    ),
  );
  const [type, setType] = useState(() =>
    initialFilter(params, 'request_type', REQUEST_TYPE_OPTIONS, ''),
  );
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const changed = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  const { dialogs, isMine, canDecide, decide } = useAdjustmentRequestActions(changed);
  const fetchPage = useCallback<FetchPage<AdjustmentRequestDto>>(
    (query, signal) => adjustmentService.listRequests(query, signal),
    [],
  );
  const columns: DataColumn<AdjustmentRequestDto>[] = [
    { id: 'at', header: 'Proposed', render: (r) => formatInstantIn(r.proposed_at, timeZone) },
    { id: 'type', header: 'Type', render: (r) => REQUEST_TYPE_LABELS[r.request_type] },
    { id: 'ref', header: 'Original record', render: (r) => r.original_reference ?? '—' },
    { id: 'cust', header: 'Customer', render: (r) => r.customer_name ?? '—' },
    {
      id: 'size',
      header: 'Hours / amount',
      align: 'right',
      render: (r) => {
        if (r.hours !== null) return hoursText(r.hours);
        if (r.amount !== null && r.currency !== null) {
          return <MoneyText amount={r.amount} currency={r.currency} />;
        }
        return '—';
      },
    },
    { id: 'why', header: 'Reason', render: (r) => r.reason_label ?? r.reason },
    {
      id: 'by',
      header: 'Proposed by',
      render: (r) => <PersonName userId={r.proposed_by} name={r.proposed_by_name} />,
    },
    {
      id: 'status',
      header: 'Status',
      render: (r) => (
        <StatusChip
          status={r.status}
          tones={REQUEST_STATUS_TONES}
          label={REQUEST_STATUS_LABELS[r.status]}
        />
      ),
    },
    {
      id: 'decide',
      header: '',
      align: 'right',
      render: (r) => {
        if (!canDecide || r.status !== 'PROPOSED') return null;
        if (isMine(r)) {
          return (
            <Tooltip title={OWN_REQUEST_TEXT}>
              <span>
                <Button size="small" disabled aria-label={`Decide (${OWN_REQUEST_TEXT})`}>
                  Decide
                </Button>
              </span>
            </Tooltip>
          );
        }
        return (
          <Button
            size="small"
            onClick={(e) => {
              e.stopPropagation();
              decide(r);
            }}
          >
            Decide
          </Button>
        );
      },
    },
  ];
  return (
    <>
      <PageHeader
        title="Adjustment requests"
        subtitle="Someone other than the proposer decides each request."
        actions={
          <Button component={RouterLink} to={ADJUSTMENT_ROUTES.ledger} variant="outlined">
            Adjustments ledger
          </Button>
        }
      />
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(r) => r.id}
        reloadKey={reloadKey}
        filters={{
          status: status === '' ? undefined : status,
          request_type: type === '' ? undefined : type,
          customer_id: customer?.id,
          machine_id: machine?.id,
          original_id: originalId,
        }}
        emptyTitle="No adjustment requests"
        onRowClick={(r) => {
          void navigate(adjustmentRequestPath(r.id));
        }}
        toolbar={
          <Box className="flex flex-wrap gap-3">
            <StaticSelectFilter
              label="Status"
              value={status}
              options={REQUEST_STATUS_OPTIONS}
              onChange={setStatus}
            />
            <StaticSelectFilter
              label="Type"
              value={type}
              options={REQUEST_TYPE_OPTIONS}
              onChange={setType}
            />
            <Box sx={{ minWidth: 220 }}>
              <CustomerFilter label="Customer" value={customer} onChange={setCustomer} />
            </Box>
            <Box sx={{ minWidth: 220 }}>
              <MachineFilter label="Machine" value={machine} onChange={setMachine} />
            </Box>
          </Box>
        }
      />
      {dialogs}
    </>
  );
}
