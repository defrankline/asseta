import { Box } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import type { CashVarianceDto } from '../../../../api/custodyTypes';
import { custodyService } from '../../../../api/services/custodyService';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { MoneyText } from '../../../../components/display/MoneyText';
import { recordPath } from '../../../../navigation/recordRoutes';
import { formatInstantIn } from '../../../../utils/time';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import {
  VARIANCE_KIND_LABELS,
  VARIANCE_SOURCE_LABELS,
  VARIANCE_STATUS_OPTIONS,
} from '../cash/custodyDisplay';
import { varianceAssignee, varianceChip, varianceCustodian } from '../cash/varianceRecord';
import { menu, useFundFilter } from './tabHelpers';

interface DifferencesTabProps {
  timeZone: string;
  /** The fund page lists one fund's differences (no fund filter). */
  fundId?: string;
  reloadKey: number;
  initialStatus?: string | undefined;
}

/**
 * Petty cash differences (count, funding, return and advance variances). Listed under the petty
 * cash capability alone (`petty_cash_only` / `petty_cash_fund_id`), so they stay reachable while
 * the cash custody controls are off. Each row opens the variance record and its follow-up.
 */
export function DifferencesTab({
  timeZone,
  fundId: fixed,
  reloadKey,
  initialStatus,
}: DifferencesTabProps) {
  const navigate = useNavigate();
  const [status, setStatus] = useState(initialStatus ?? '');
  const { fundId, filter } = useFundFilter(fixed);
  const fetchPage = useCallback<FetchPage<CashVarianceDto>>(
    (query, signal) => custodyService.variances(query, signal),
    [],
  );
  const view = (v: CashVarianceDto) => {
    void navigate(recordPath('CASH_VARIANCE', v.id));
  };
  const columns: DataColumn<CashVarianceDto>[] = [
    { id: 'at', header: 'Opened', render: (v) => formatInstantIn(v.opened_at, timeZone) },
    ...(fixed === undefined
      ? [
          {
            id: 'fund',
            header: 'Fund',
            render: (v: CashVarianceDto) => v.petty_cash_fund_name ?? '—',
          },
        ]
      : []),
    { id: 'source', header: 'From', render: (v) => VARIANCE_SOURCE_LABELS[v.source_type] },
    { id: 'kind', header: 'Kind', render: (v) => VARIANCE_KIND_LABELS[v.kind] },
    { id: 'who', header: 'Accountable', render: varianceCustodian },
    { id: 'assignee', header: 'Assigned to', render: varianceAssignee },
    { id: 'status', header: 'Status', render: varianceChip },
    {
      id: 'diff',
      header: 'Difference',
      align: 'right',
      render: (v) => <MoneyText amount={v.amount} currency={v.currency} strong />,
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (v) =>
        menu(
          `difference ${VARIANCE_SOURCE_LABELS[v.source_type]}`,
          () => {
            view(v);
          },
          [],
        ),
    },
  ];
  return (
    <ServerDataTable<CashVarianceDto>
      columns={columns}
      fetchPage={fetchPage}
      getRowId={(v) => v.id}
      searchable={false}
      reloadKey={reloadKey}
      filters={{
        petty_cash_only: 'true',
        petty_cash_fund_id: fundId,
        status: status || undefined,
      }}
      emptyTitle="No petty cash differences"
      emptyDescription="A count, funding, return or advance that does not match opens a difference here."
      onRowClick={view}
      toolbar={
        <Box className="flex flex-wrap items-center gap-3">
          {filter}
          <StaticSelectFilter
            label="Status"
            value={status}
            options={VARIANCE_STATUS_OPTIONS}
            onChange={setStatus}
          />
        </Box>
      }
    />
  );
}
