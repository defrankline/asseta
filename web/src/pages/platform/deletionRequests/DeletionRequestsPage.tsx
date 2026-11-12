import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import {
  companyClosureService,
  DELETION_STATUSES,
  type CompanyDeletionRequestDto,
} from '../../../api/services/companyClosureService';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { deletionRequestDetailPath } from '../../../navigation/routes';
import { formatDateIn, formatInstantIn } from '../../../utils/time';
import {
  DELETION_STATUS_LABELS,
  DELETION_STATUS_TONES,
} from '../../tenant/companyClosure/closureDisplay';

const STATUS_OPTIONS = DELETION_STATUSES.map((s) => ({
  value: s,
  label: DELETION_STATUS_LABELS[s],
}));

/**
 * Tenants -> Deletion requests (`platform.tenant.deletion.read`): every company closure request and
 * how far its deletion has gone.
 */
export function DeletionRequestsPage() {
  const navigate = useNavigate();
  const timeZone = useDisplayTimeZone();
  const [status, setStatus] = useState('');
  const filters = useMemo(() => ({ status: status || undefined }), [status]);
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      companyClosureService.list(
        { page: q.page, page_size: q.page_size, filters: q.filters },
        signal,
      ),
    [],
  );
  const columns: DataColumn<CompanyDeletionRequestDto>[] = [
    { id: 'company', header: 'Company', render: (r) => r.tenant_name },
    {
      id: 'status',
      header: 'Status',
      render: (r) => (
        <StatusChip
          status={r.status}
          tones={DELETION_STATUS_TONES}
          label={DELETION_STATUS_LABELS[r.status]}
        />
      ),
    },
    { id: 'by', header: 'Requested by', render: (r) => r.requested_by_name ?? '—' },
    { id: 'at', header: 'Requested', render: (r) => formatInstantIn(r.requested_at, timeZone) },
    {
      id: 'scheduled',
      header: 'Deletion date',
      render: (r) => formatDateIn(r.scheduled_for, timeZone),
    },
    { id: 'attempts', header: 'Attempts', align: 'right', render: (r) => r.attempts },
  ];
  return (
    <>
      <PageHeader
        title="Deletion requests"
        subtitle="Company closures: waiting, cancelled, in progress and deleted"
      />
      <ServerDataTable<CompanyDeletionRequestDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(r) => r.id}
        filters={filters}
        searchable={false}
        isRowMuted={(r) => r.status === 'CANCELLED'}
        onRowClick={(r) => {
          void navigate(deletionRequestDetailPath(r.id));
        }}
        toolbar={
          <StaticSelectFilter
            label="Status"
            value={status}
            options={STATUS_OPTIONS}
            onChange={setStatus}
          />
        }
        emptyTitle="No deletion requests"
        emptyDescription="Requests appear here when a company owner asks to close the company."
      />
    </>
  );
}
