import Add from '@mui/icons-material/Add';
import { Alert, Button, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import type { TransferDto } from '../../../api/hoursTypes';
import { hoursRequestService } from '../../../api/services/hoursService';
import { ServerDataTable } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { useNotify } from '../../../notifications/useNotify';
import { HoursOffNotice } from './HoursDialogs';
import { REQUEST_STATUS_OPTIONS } from './hoursDisplay';
import { RequestTransferDialog } from './PurchaseActionDialogs';
import { useTransferRequests } from './useHoursRequests';
import { useHoursPolicy } from './useHoursPolicy';

/** Hours transfers between machines: awaiting a decision by default; request, decide, withdraw. */
export function HoursTransfersPage() {
  const notify = useNotify();
  const hours = useHoursPolicy();
  const canRequest = useCanMutate(PERMISSIONS.tenantHoursTransfer) && hours.on;
  const [status, setStatus] = useState('PENDING');
  const [requesting, setRequesting] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  const { columns, dialogs } = useTransferRequests(reload, { showPurchase: true });
  const fetchPage = useCallback<FetchPage<TransferDto>>(
    (query, signal) => hoursRequestService.listTransfers(query, signal),
    [],
  );
  return (
    <>
      <PageHeader
        title="Hours transfers"
        subtitle="Remaining prepaid hours moved from one machine to another"
        actions={
          canRequest && (
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setRequesting(true);
              }}
            >
              Request transfer
            </Button>
          )
        }
      />
      <Stack spacing={2}>
        <HoursOffNotice off={hours.status === 'known' && !hours.on} />
        <Alert severity="info">
          A transfer moves only hours not yet used. The person who requested it cannot decide it.
        </Alert>
        <ServerDataTable
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(t) => t.id}
          searchable={false}
          reloadKey={reloadKey}
          filters={{ status: status === '' ? undefined : status }}
          emptyTitle={status === 'PENDING' ? 'No transfers awaiting a decision' : 'No transfers'}
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
      {requesting && (
        <RequestTransferDialog
          reasonCodeRequired={hours.policy?.reasonCodeRequired ?? false}
          onClose={() => {
            setRequesting(false);
          }}
          onDone={() => {
            notify.success('Transfer requested; someone else decides it.');
            reload();
          }}
        />
      )}
    </>
  );
}
