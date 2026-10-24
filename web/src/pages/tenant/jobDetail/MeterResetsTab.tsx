import { Alert, Box, Button, Stack, Tooltip } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { meterService } from '../../../api/services/meterService';
import type { ResetDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { AttachmentPhoto } from '../../../components/meter/AttachmentPhoto';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { RESET_TONES } from '../shared/jobDisplay';
import { DecideResetDialog } from './DecideResetDialog';
import { RequestResetDialog } from './RequestResetDialog';

export const OWN_RESET_TEXT = 'You requested this reset; another approver must decide it.';

interface MeterResetsTabProps {
  machineId: string;
  machineName: string;
  timeZone: string;
}

/** Documented meter reset/replacement events for the machine; requesters and approvers differ. */
export function MeterResetsTab({ machineId, machineName, timeZone }: MeterResetsTabProps) {
  const notify = useNotify();
  const { me, hasPermission } = useSession();
  const canRequest = useCanMutate(PERMISSIONS.tenantMeterCapture);
  const canDecide = useCanMutate(PERMISSIONS.tenantMeterApprove);
  const canViewEvidence = hasPermission(PERMISSIONS.tenantMeterRead);
  const [requesting, setRequesting] = useState(false);
  const [deciding, setDeciding] = useState<ResetDto | null>(null);
  const load = useCallback(
    (signal: AbortSignal) => meterService.listResets({ machine_id: machineId }, signal),
    [machineId],
  );
  const resource = useAsyncResource(load);
  const columns: DataColumn<ResetDto>[] = [
    { id: 'old', header: 'Old', align: 'right', render: (r) => r.old_reading },
    { id: 'new', header: 'New', align: 'right', render: (r) => r.new_reading },
    { id: 'at', header: 'Effective', render: (r) => formatInstantIn(r.effective_at, timeZone) },
    { id: 'reason', header: 'Reason', render: (r) => r.reason },
    {
      id: 'status',
      header: 'Status',
      render: (r) => <StatusChip status={r.status} tones={RESET_TONES} />,
    },
    {
      id: 'evidence',
      header: 'Evidence',
      render: (r) =>
        r.evidence_attachment_id !== null && canViewEvidence ? (
          <AttachmentPhoto
            attachmentId={r.evidence_attachment_id}
            fetchUrl={(id) => meterService.attachmentUrl(id)}
            label="View evidence"
          />
        ) : r.evidence_attachment_id !== null ? (
          'On file'
        ) : (
          '—'
        ),
    },
    {
      id: 'decide',
      header: '',
      align: 'right',
      render: (r) => {
        if (!canDecide || r.status !== 'PENDING') return null;
        const own = me !== null && r.requested_by === me.user_id;
        return own ? (
          <Tooltip title={OWN_RESET_TEXT}>
            <span>
              <Button size="small" disabled aria-label={`Decide reset (${OWN_RESET_TEXT})`}>
                Decide
              </Button>
            </span>
          </Tooltip>
        ) : (
          <Button
            size="small"
            onClick={() => {
              setDeciding(r);
            }}
          >
            Decide
          </Button>
        );
      },
    },
  ];
  return (
    <Stack spacing={2}>
      <Alert severity="info">
        A meter reset documents a replaced or rolled-over hour meter. It needs approval by someone
        other than the requester before later readings are compared against the new value.
      </Alert>
      {canRequest && (
        <Box className="flex justify-end">
          <Button
            variant="contained"
            onClick={() => {
              setRequesting(true);
            }}
          >
            Request meter reset
          </Button>
        </Box>
      )}
      <AsyncContent
        resource={resource}
        isEmpty={(d) => d.length === 0}
        emptyTitle="No meter resets for this machine"
        errorTitle="Could not load meter resets"
      >
        {(d) => (
          <StaticTable ariaLabel="Meter resets" columns={columns} rows={d} getRowId={(r) => r.id} />
        )}
      </AsyncContent>
      {requesting && (
        <RequestResetDialog
          machineId={machineId}
          machineName={machineName}
          timeZone={timeZone}
          onClose={() => {
            setRequesting(false);
          }}
          onRequested={() => {
            notify.success('Meter reset requested; it awaits another approver.');
            resource.reload();
          }}
        />
      )}
      {deciding !== null && (
        <DecideResetDialog
          reset={deciding}
          timeZone={timeZone}
          onClose={() => {
            setDeciding(null);
          }}
          onDecided={(r) => {
            notify.success(`Meter reset ${r.status.toLowerCase()}.`);
            resource.reload();
          }}
        />
      )}
    </Stack>
  );
}
