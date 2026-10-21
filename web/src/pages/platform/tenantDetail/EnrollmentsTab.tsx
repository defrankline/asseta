import { Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { Can } from '../../../access/Can';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { subscriptionService } from '../../../api/services/subscriptionService';
import type { EnrollmentDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useNotify } from '../../../notifications/useNotify';
import { formatDate } from '../../../utils/dates';
import { formatMoney } from '../../../utils/money';
import { END_REASON_OPTIONS, optionLabel } from '../shared/billingDisplay';
import { EndEnrollmentDialog } from './EndEnrollmentDialog';

interface EnrollmentsTabProps {
  subscriptionId: string;
  /** Called after an enrollment ended (subscription counts / pending charges change). */
  onChanged: () => void;
}

export function EnrollmentsTab({ subscriptionId, onChanged }: EnrollmentsTabProps) {
  const notify = useNotify();
  const [ending, setEnding] = useState<EnrollmentDto | null>(null);
  const load = useCallback(
    (signal: AbortSignal) => subscriptionService.listEnrollments(subscriptionId, signal),
    [subscriptionId],
  );
  const enrollments = useAsyncResource(load);

  const columns: DataColumn<EnrollmentDto>[] = [
    { id: 'asset', header: 'Asset', render: (e) => e.asset_label },
    { id: 'from', header: 'From', render: (e) => formatDate(e.effective_from) },
    { id: 'to', header: 'To', render: (e) => formatDate(e.effective_to) },
    {
      id: 'state',
      header: 'State',
      render: (e) =>
        e.effective_to === null ? (
          <StatusChip status="ACTIVE" tones={{ ACTIVE: 'success' }} label="Billable" />
        ) : (
          <StatusChip
            status="ENDED"
            label={e.end_reason !== null ? optionLabel(END_REASON_OPTIONS, e.end_reason) : 'Ended'}
          />
        ),
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (e) =>
        e.effective_to === null ? (
          <Can permission={PERMISSIONS.platformEnrollmentManage}>
            <Button
              size="small"
              color="error"
              onClick={() => {
                setEnding(e);
              }}
            >
              End enrollment
            </Button>
          </Can>
        ) : null,
    },
  ];

  return (
    <Box>
      <AsyncContent
        resource={enrollments}
        isEmpty={(r) => r.length === 0}
        emptyTitle="No enrolled assets"
        emptyDescription="Tenants enroll machines as billable assets from the tenant console."
      >
        {(rows) => (
          <StaticTable
            ariaLabel="Enrollments"
            columns={columns}
            rows={rows}
            getRowId={(e) => e.id}
          />
        )}
      </AsyncContent>
      {ending !== null && (
        <EndEnrollmentDialog
          subscriptionId={subscriptionId}
          enrollment={ending}
          onClose={() => {
            setEnding(null);
          }}
          onEnded={(r) => {
            notify.success(
              r.charge === null
                ? 'Enrollment ended.'
                : `Enrollment ended; pending ${formatMoney(r.charge.amount, r.charge.currency)} recorded.`,
            );
            enrollments.reload();
            onChanged();
          }}
        />
      )}
    </Box>
  );
}
