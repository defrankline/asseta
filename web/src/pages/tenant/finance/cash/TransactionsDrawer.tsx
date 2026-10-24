import { Link, Typography } from '@mui/material';
import { useCallback } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { custodyService } from '../../../../api/services/custodyService';
import type { CustodyTransactionDto, ReconciliationFigure } from '../../../../api/custodyTypes';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { CopyButton } from '../../../../components/display/CopyButton';
import { MoneyText } from '../../../../components/display/MoneyText';
import { DetailsDrawer } from '../../../../components/lifecycle/DetailsDrawer';
import { useSession } from '../../../../session/useSession';
import { formatDate } from '../../../../utils/dates';
import { humanize } from '../../../../utils/text';
import { formatInstantIn } from '../../../../utils/time';
import { PersonName } from '../../shared/PersonName';
import { entityTypeLabel, FIGURE_LABELS, transactionRecordPath } from './custodyDisplay';
import { useCustodianLabels } from './custodyHooks';

export interface DrillDown {
  /** Omitted: the caller's own custody (field work). */
  staffMemberId?: string | undefined;
  from: string;
  to: string;
  currency: string;
  figure: ReconciliationFigure;
}

/** The transactions behind one reconciliation figure, each with the record holding its evidence. */
export function TransactionsDrawer({
  drill,
  timeZone,
  onClose,
}: {
  drill: DrillDown;
  timeZone: string;
  onClose: () => void;
}) {
  const { hasPermission } = useSession();
  const office = drill.staffMemberId !== undefined && hasPermission(PERMISSIONS.tenantFinanceRead);
  const custodian = useCustodianLabels();
  const fetchPage = useCallback<FetchPage<CustodyTransactionDto>>(
    (query, signal) =>
      custodyService.transactions(
        {
          staffMemberId: drill.staffMemberId,
          from: drill.from,
          to: drill.to,
          currency: drill.currency,
          figure: drill.figure,
          page: query.page,
          page_size: query.page_size,
        },
        signal,
      ),
    [drill],
  );
  const columns: DataColumn<CustodyTransactionDto>[] = [
    { id: 'at', header: 'When', render: (t) => formatInstantIn(t.occurred_at, timeZone) },
    {
      id: 'record',
      header: 'Record',
      render: (t) => {
        const to = office ? transactionRecordPath(t) : null;
        const text = `${entityTypeLabel(t.entity_type)}${t.reference === null ? '' : ` · ${t.reference}`}`;
        return to === null ? (
          text
        ) : (
          <Link component={RouterLink} to={to} underline="hover">
            {text}
          </Link>
        );
      },
    },
    { id: 'status', header: 'Status', render: (t) => humanize(t.status) },
    {
      id: 'counterparty',
      header: 'Other custodian',
      render: (t) => (t.counterparty_staff_id === null ? '—' : custodian(t.counterparty_staff_id)),
    },
    { id: 'by', header: 'Recorded by', render: (t) => <PersonName userId={t.recorded_by} /> },
    { id: 'note', header: 'Note', render: (t) => t.note ?? '—' },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (t) => <MoneyText amount={t.amount} currency={t.currency} />,
    },
    {
      id: 'id',
      header: '',
      align: 'right',
      render: (t) => <CopyButton value={t.entity_id} label="Copy id" />,
    },
  ];
  const period =
    drill.from === drill.to
      ? formatDate(drill.from)
      : `${formatDate(drill.from)} – ${formatDate(drill.to)}`;
  return (
    <DetailsDrawer title={FIGURE_LABELS[drill.figure]} onClose={onClose}>
      <Typography variant="body2" color="text.secondary">
        {drill.staffMemberId === undefined ? 'My custody' : custodian(drill.staffMemberId)} ·{' '}
        {drill.currency} · {period}
      </Typography>
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(t) => `${t.entity_type}:${t.entity_id}:${t.figure}`}
        searchable={false}
        emptyTitle="No transactions behind this figure"
      />
    </DetailsDrawer>
  );
}
