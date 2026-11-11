import { Box } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { inactiveFilter } from '../../../../api/lifecycle';
import type { PettyCashFundDto, PettyCashMovementDto } from '../../../../api/pettyCashTypes';
import { pettyCashService } from '../../../../api/services/pettyCashService';
import type { StaffDto } from '../../../../api/types';
import { ExportMenu } from '../../../../components/data/ExportMenu';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { ActiveChip } from '../../../../components/lifecycle/ActiveChip';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import { ShowInactiveToggle } from '../../../../components/lifecycle/ShowInactiveToggle';
import { pettyCashFundPath, pettyCashPath } from '../../../../navigation/pettyCashRoutes';
import { formatInstantIn } from '../../../../utils/time';
import { StaffFilter } from '../../shared/financePickers';
import { useFundActions, useMovementActions } from './pettyCashActions';
import {
  FUNDING_STATUS_OPTIONS,
  MOVEMENT_KIND_LABELS,
  MOVEMENT_STATUS_LABELS,
  MOVEMENT_STATUS_TONES,
  RETURN_STATUS_OPTIONS,
} from './pettyCashDisplay';
import { menu, useFundFilter, type TabProps } from './tabHelpers';

/** Balance and available to spend of a listed fund (`with_balance`). */
const balanceOf = (f: PettyCashFundDto, key: 'balance' | 'available_to_spend') =>
  f.balance == null ? '—' : <MoneyText amount={f.balance[key]} currency={f.currency} />;

/** Funds: search, holder filter, inactive, paging; every lifecycle command in the row menu. */
export function FundsTab({ holds, reloadKey, onChanged }: Omit<TabProps, 'fundId' | 'timeZone'>) {
  const navigate = useNavigate();
  const [holder, setHolder] = useState<StaffDto | null>(null);
  const [showInactive, setShowInactive] = useState(false);
  const view = (f: PettyCashFundDto) => {
    void navigate(pettyCashFundPath(f.id));
  };
  const { actionsFor, dialogs } = useFundActions({ holds, onChanged, onView: view });
  const filters = useMemo(
    () => ({ holder_staff_id: holder?.id, ...inactiveFilter(showInactive) }),
    [holder, showInactive],
  );
  const fetchPage = useCallback<FetchPage<PettyCashFundDto>>(
    (query, signal) => pettyCashService.funds(query, signal),
    [],
  );
  const columns: DataColumn<PettyCashFundDto>[] = [
    { id: 'code', header: 'Code', render: (f) => <strong>{f.code}</strong> },
    { id: 'name', header: 'Name', render: (f) => f.name },
    { id: 'holder', header: 'Holder', render: (f) => f.holder_staff_name ?? '—' },
    { id: 'site', header: 'Job site', render: (f) => f.job_site_name ?? '—' },
    {
      id: 'limit',
      header: 'Approved limit',
      align: 'right',
      render: (f) => <MoneyText amount={f.approved_limit} currency={f.currency} />,
    },
    { id: 'balance', header: 'Balance', align: 'right', render: (f) => balanceOf(f, 'balance') },
    {
      id: 'available',
      header: 'Available to spend',
      align: 'right',
      render: (f) => balanceOf(f, 'available_to_spend'),
    },
    {
      id: 'state',
      header: 'State',
      render: (f) =>
        f.balance?.below_low_balance === true && f.is_active ? (
          <StatusChip status="LOW" tones={{ LOW: 'warning' }} label="Running low" />
        ) : (
          <ActiveChip active={f.is_active} />
        ),
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (f) => <RowActionsMenu label={f.name} actions={actionsFor(f)} />,
    },
  ];
  return (
    <>
      <ServerDataTable<PettyCashFundDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(f) => f.id}
        filters={filters}
        searchPlaceholder="Search code or name"
        emptyTitle="No petty cash funds"
        emptyDescription="A fund is a cash box with one accountable holder and an approved limit."
        reloadKey={reloadKey}
        isRowMuted={(f) => !f.is_active}
        onRowClick={view}
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center gap-3">
            <Box sx={{ minWidth: 240 }}>
              <StaffFilter label="Holder" value={holder} onChange={setHolder} />
            </Box>
            <ShowInactiveToggle checked={showInactive} onChange={setShowInactive} />
            <Box className="flex-1" />
            <ExportMenu reports={[{ code: 'petty_cash_expenses', filters: {} }]} />
          </Box>
        }
      />
      {dialogs}
    </>
  );
}

/** Fundings and top-ups (`group="fundings"`) or returns (`group="returns"`). */
export function MovementsTab({
  timeZone,
  fundId: fixed,
  holds,
  reloadKey,
  onChanged,
  initialStatus,
  group,
}: TabProps & { group: 'fundings' | 'returns' }) {
  const navigate = useNavigate();
  const [status, setStatus] = useState(initialStatus ?? '');
  const [kind, setKind] = useState('');
  const { fundId, filter } = useFundFilter(fixed);
  const { actionsFor, dialog } = useMovementActions(holds, onChanged);
  const returns = group === 'returns';
  const fetchPage = useCallback<FetchPage<PettyCashMovementDto>>(
    (query, signal) => pettyCashService.movements(query, signal),
    [],
  );
  const view = (m: PettyCashMovementDto) => {
    void navigate(pettyCashPath('movements', m.id));
  };
  const columns: DataColumn<PettyCashMovementDto>[] = [
    { id: 'number', header: 'Number', render: (m) => <strong>{m.number}</strong> },
    {
      id: 'at',
      header: returns ? 'Recorded' : 'Proposed',
      render: (m) => formatInstantIn(m.created_at, timeZone),
    },
    ...(fixed === undefined
      ? [
          {
            id: 'fund',
            header: 'Fund',
            render: (m: PettyCashMovementDto) => m.petty_cash_fund_name ?? '—',
          },
        ]
      : []),
    ...(returns
      ? []
      : [
          {
            id: 'kind',
            header: 'Kind',
            render: (m: PettyCashMovementDto) => MOVEMENT_KIND_LABELS[m.kind],
          },
        ]),
    {
      id: 'by',
      header: returns ? 'Recorded by' : 'Proposed by',
      render: (m) => m.created_by_name ?? '—',
    },
    {
      id: 'status',
      header: 'Status',
      render: (m) => (
        <StatusChip
          status={m.status}
          tones={MOVEMENT_STATUS_TONES}
          label={MOVEMENT_STATUS_LABELS[m.status]}
        />
      ),
    },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (m) => <MoneyText amount={m.amount} currency={m.currency} />,
    },
    {
      id: 'received',
      header: returns ? 'Counted' : 'Received',
      align: 'right',
      render: (m) =>
        m.amount_received == null ? (
          '—'
        ) : (
          <MoneyText amount={m.amount_received} currency={m.currency} />
        ),
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (m) =>
        menu(
          m.number,
          () => {
            view(m);
          },
          actionsFor(m),
        ),
    },
  ];
  return (
    <>
      <ServerDataTable<PettyCashMovementDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(m) => m.id}
        searchPlaceholder="Search number or reference"
        reloadKey={reloadKey}
        filters={{
          fund_id: fundId,
          kind: returns ? 'RETURN' : kind || undefined,
          status: status || undefined,
        }}
        emptyTitle={returns ? 'No returns' : 'No fundings or top-ups'}
        isRowMuted={(m) => m.status === 'REJECTED'}
        onRowClick={view}
        toolbar={
          <Box className="flex flex-wrap items-center gap-3">
            {filter}
            {!returns && (
              <StaticSelectFilter
                label="Kind"
                value={kind}
                options={KIND_FILTER_OPTIONS}
                onChange={setKind}
              />
            )}
            <StaticSelectFilter
              label="Status"
              value={status}
              options={MOVEMENT_STATUS_CHOICES[group]}
              onChange={setStatus}
            />
          </Box>
        }
      />
      {dialog}
    </>
  );
}

const MOVEMENT_STATUS_CHOICES = {
  fundings: FUNDING_STATUS_OPTIONS,
  returns: RETURN_STATUS_OPTIONS,
} as const;

const KIND_FILTER_OPTIONS = [
  { value: 'FUNDING', label: 'Fundings' },
  { value: 'TOP_UP', label: 'Top-ups' },
] as const;
