import { Alert, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import type { CancellationDto } from '../../../api/hoursTypes';
import { hoursRequestService } from '../../../api/services/hoursService';
import { ServerDataTable } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { recordPath } from '../../../navigation/recordRoutes';
import { REQUEST_STATUS_OPTIONS } from './hoursDisplay';
import { useCancellationRequests } from './useHoursRequests';

/** Hours purchase cancellation requests: awaiting a decision by default; decide or withdraw. */
export function HoursCancellationsPage() {
  const [status, setStatus] = useState('PENDING');
  const navigate = useNavigate();
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  const { columns, dialogs } = useCancellationRequests(reload, { showPurchase: true });
  const fetchPage = useCallback<FetchPage<CancellationDto>>(
    (query, signal) => hoursRequestService.listCancellations(query, signal),
    [],
  );
  return (
    <>
      <PageHeader
        title="Hours cancellations"
        subtitle="Requests to cancel hours purchases (requested from the purchase page)"
      />
      <Stack spacing={2}>
        <Alert severity="info">
          Approving cancels the hours not yet used. The person who requested it cannot decide it.
        </Alert>
        <ServerDataTable
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(c) => c.id}
          onRowClick={(c) => {
            void navigate(recordPath('HOURS_CANCELLATION', c.id));
          }}
          searchable={false}
          reloadKey={reloadKey}
          filters={{ status: status === '' ? undefined : status }}
          emptyTitle={
            status === 'PENDING' ? 'No cancellations awaiting a decision' : 'No cancellations'
          }
          toolbar={
            <StaticSelectFilter
              label="Status"
              value={status}
              options={REQUEST_STATUS_OPTIONS}
              allLabel="All statuses"
              onChange={setStatus}
            />
          }
        />
      </Stack>
      {dialogs}
    </>
  );
}
