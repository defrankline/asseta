import { Box } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import type {
  PettyCashAdjustmentDto,
  PettyCashAdvanceDto,
  PettyCashCountDto,
  PettyCashHolderChangeDto,
} from '../../../../api/pettyCashTypes';
import { pettyCashService } from '../../../../api/services/pettyCashService';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { pettyCashPath } from '../../../../navigation/pettyCashRoutes';
import { formatInstantIn } from '../../../../utils/time';
import { useAdjustmentActions, useAdvanceActions, useHolderChangeActions } from './recordActions';
import {
  ADJUSTMENT_STATUS_OPTIONS,
  ADVANCE_LABELS,
  ADVANCE_STATUS_OPTIONS,
  ADVANCE_TONES,
  COUNT_REASON_LABELS,
  DECISION_LABELS,
  DECISION_TONES,
  HOLDER_CHANGE_LABELS,
  HOLDER_CHANGE_STATUS_OPTIONS,
  HOLDER_CHANGE_TONES,
} from './pettyCashDisplay';
import { menu, useFundFilter, type TabProps } from './tabHelpers';

/** Physical counts with the expected cash and the difference (a difference opens a variance). */
export function CountsTab({ timeZone, fundId: fixed, reloadKey }: TabProps) {
  const navigate = useNavigate();
  const { fundId, filter } = useFundFilter(fixed);
  const fetchPage = useCallback<FetchPage<PettyCashCountDto>>(
    (query, signal) => pettyCashService.counts(query, signal),
    [],
  );
  const view = (c: PettyCashCountDto) => {
    void navigate(pettyCashPath('counts', c.id));
  };
  const columns: DataColumn<PettyCashCountDto>[] = [
    { id: 'number', header: 'Number', render: (c) => <strong>{c.number}</strong> },
    { id: 'at', header: 'Counted', render: (c) => formatInstantIn(c.counted_at, timeZone) },
    ...(fixed === undefined
      ? [
          {
            id: 'fund',
            header: 'Fund',
            render: (c: PettyCashCountDto) => c.petty_cash_fund_name ?? '—',
          },
        ]
      : []),
    { id: 'reason', header: 'Why', render: (c) => COUNT_REASON_LABELS[c.reason] },
    {
      id: 'by',
      header: 'Counted by',
      render: (c) =>
        `${c.counted_by_name ?? '—'}${c.witness_user_name == null ? '' : ` with ${c.witness_user_name}`}${c.self_count ? ' (self-count)' : ''}`,
    },
    {
      id: 'expected',
      header: 'Expected',
      align: 'right',
      render: (c) => <MoneyText amount={c.expected_amount} currency={c.currency} />,
    },
    {
      id: 'counted',
      header: 'Counted',
      align: 'right',
      render: (c) => <MoneyText amount={c.counted_amount} currency={c.currency} />,
    },
    {
      id: 'diff',
      header: 'Difference',
      align: 'right',
      render: (c) => <MoneyText amount={c.difference} currency={c.currency} strong />,
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (c) =>
        menu(
          c.number,
          () => {
            view(c);
          },
          [],
        ),
    },
  ];
  return (
    <ServerDataTable<PettyCashCountDto>
      columns={columns}
      fetchPage={fetchPage}
      getRowId={(c) => c.id}
      searchPlaceholder="Search number"
      reloadKey={reloadKey}
      filters={{ fund_id: fundId }}
      emptyTitle="No counts"
      onRowClick={view}
      toolbar={filter}
    />
  );
}

export function HolderChangesTab({
  timeZone,
  fundId: fixed,
  holds,
  reloadKey,
  onChanged,
  initialStatus,
}: TabProps) {
  const navigate = useNavigate();
  const [status, setStatus] = useState(initialStatus ?? '');
  const { fundId, filter } = useFundFilter(fixed);
  const { actionsFor, dialog } = useHolderChangeActions(holds, onChanged);
  const fetchPage = useCallback<FetchPage<PettyCashHolderChangeDto>>(
    (query, signal) => pettyCashService.holderChanges(query, signal),
    [],
  );
  const view = (c: PettyCashHolderChangeDto) => {
    void navigate(pettyCashPath('holder-changes', c.id));
  };
  const columns: DataColumn<PettyCashHolderChangeDto>[] = [
    { id: 'at', header: 'Started', render: (c) => formatInstantIn(c.requested_at, timeZone) },
    ...(fixed === undefined
      ? [
          {
            id: 'fund',
            header: 'Fund',
            render: (c: PettyCashHolderChangeDto) => c.petty_cash_fund_name ?? '—',
          },
        ]
      : []),
    { id: 'from', header: 'From', render: (c) => c.from_staff_name ?? '—' },
    { id: 'to', header: 'To', render: (c) => c.to_staff_name ?? '—' },
    {
      id: 'status',
      header: 'Status',
      render: (c) => (
        <StatusChip
          status={c.status}
          tones={HOLDER_CHANGE_TONES}
          label={HOLDER_CHANGE_LABELS[c.status]}
        />
      ),
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (c) =>
        menu(
          'holder change',
          () => {
            view(c);
          },
          actionsFor(c),
        ),
    },
  ];
  return (
    <>
      <ServerDataTable<PettyCashHolderChangeDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(c) => c.id}
        searchable={false}
        reloadKey={reloadKey}
        filters={{ fund_id: fundId, status: status || undefined }}
        emptyTitle="No holder changes"
        onRowClick={view}
        toolbar={
          <Box className="flex flex-wrap items-center gap-3">
            {filter}
            <StaticSelectFilter
              label="Status"
              value={status}
              options={HOLDER_CHANGE_STATUS_OPTIONS}
              onChange={setStatus}
            />
          </Box>
        }
      />
      {dialog}
    </>
  );
}

export function AdjustmentsTab({
  timeZone,
  fundId: fixed,
  holds,
  reloadKey,
  onChanged,
  initialStatus,
}: TabProps) {
  const navigate = useNavigate();
  const [status, setStatus] = useState(initialStatus ?? '');
  const { fundId, filter } = useFundFilter(fixed);
  const { actionsFor, dialog } = useAdjustmentActions(holds, onChanged);
  const fetchPage = useCallback<FetchPage<PettyCashAdjustmentDto>>(
    (query, signal) => pettyCashService.adjustments(query, signal),
    [],
  );
  const view = (a: PettyCashAdjustmentDto) => {
    void navigate(pettyCashPath('adjustments', a.id));
  };
  const columns: DataColumn<PettyCashAdjustmentDto>[] = [
    { id: 'number', header: 'Number', render: (a) => <strong>{a.number}</strong> },
    { id: 'at', header: 'Proposed', render: (a) => formatInstantIn(a.created_at, timeZone) },
    ...(fixed === undefined
      ? [
          {
            id: 'fund',
            header: 'Fund',
            render: (a: PettyCashAdjustmentDto) => a.petty_cash_fund_name ?? '—',
          },
        ]
      : []),
    { id: 'reason', header: 'Reason', render: (a) => a.reason },
    { id: 'by', header: 'Proposed by', render: (a) => a.created_by_name ?? '—' },
    {
      id: 'status',
      header: 'Status',
      render: (a) => (
        <StatusChip status={a.status} tones={DECISION_TONES} label={DECISION_LABELS[a.status]} />
      ),
    },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (a) => <MoneyText amount={a.amount} currency={a.currency} />,
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (a) =>
        menu(
          a.number,
          () => {
            view(a);
          },
          actionsFor(a),
        ),
    },
  ];
  return (
    <>
      <ServerDataTable<PettyCashAdjustmentDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(a) => a.id}
        searchPlaceholder="Search number or reason"
        reloadKey={reloadKey}
        filters={{ fund_id: fundId, status: status || undefined }}
        emptyTitle="No adjustments"
        isRowMuted={(a) => a.status === 'REJECTED'}
        onRowClick={view}
        toolbar={
          <Box className="flex flex-wrap items-center gap-3">
            {filter}
            <StaticSelectFilter
              label="Status"
              value={status}
              options={ADJUSTMENT_STATUS_OPTIONS}
              onChange={setStatus}
            />
          </Box>
        }
      />
      {dialog}
    </>
  );
}

export function AdvancesTab({
  timeZone,
  fundId: fixed,
  holds,
  reloadKey,
  onChanged,
  initialStatus,
}: TabProps) {
  const navigate = useNavigate();
  const [status, setStatus] = useState(initialStatus ?? '');
  const { fundId, filter } = useFundFilter(fixed);
  const { actionsFor, dialog } = useAdvanceActions(holds, onChanged);
  const fetchPage = useCallback<FetchPage<PettyCashAdvanceDto>>(
    (query, signal) => pettyCashService.advances(query, signal),
    [],
  );
  const view = (a: PettyCashAdvanceDto) => {
    void navigate(pettyCashPath('advances', a.id));
  };
  const columns: DataColumn<PettyCashAdvanceDto>[] = [
    { id: 'number', header: 'Number', render: (a) => <strong>{a.number}</strong> },
    { id: 'at', header: 'Paid', render: (a) => formatInstantIn(a.issued_at, timeZone) },
    ...(fixed === undefined
      ? [
          {
            id: 'fund',
            header: 'Fund',
            render: (a: PettyCashAdvanceDto) => a.petty_cash_fund_name ?? '—',
          },
        ]
      : []),
    { id: 'to', header: 'Paid to', render: (a) => a.recipient_staff_name ?? '—' },
    { id: 'purpose', header: 'For', render: (a) => a.purpose },
    {
      id: 'due',
      header: 'Clear by',
      render: (a) => `${formatInstantIn(a.due_at, timeZone)}${a.overdue ? ' (past due)' : ''}`,
    },
    {
      id: 'status',
      header: 'Status',
      render: (a) => (
        <StatusChip status={a.status} tones={ADVANCE_TONES} label={ADVANCE_LABELS[a.status]} />
      ),
    },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (a) => <MoneyText amount={a.amount} currency={a.currency} />,
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (a) =>
        menu(
          a.number,
          () => {
            view(a);
          },
          actionsFor(a),
        ),
    },
  ];
  return (
    <>
      <ServerDataTable<PettyCashAdvanceDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(a) => a.id}
        searchPlaceholder="Search number or purpose"
        reloadKey={reloadKey}
        filters={{ fund_id: fundId, status: status || undefined }}
        emptyTitle="No advances"
        onRowClick={view}
        toolbar={
          <Box className="flex flex-wrap items-center gap-3">
            {filter}
            <StaticSelectFilter
              label="Status"
              value={status}
              options={ADVANCE_STATUS_OPTIONS}
              onChange={setStatus}
            />
          </Box>
        }
      />
      {dialog}
    </>
  );
}
