import { Alert, Box, Button, Stack, Tooltip } from '@mui/material';
import { useCallback, useState } from 'react';
import { useParams, useSearchParams } from 'react-router';
import { initialFilter } from '../../../navigation/urlFilters';
import { FocusMissingAlert } from '../shared/FocusMissingAlert';
import { useRecordById } from '../shared/useRecordById';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { meterService } from '../../../api/services/meterService';
import type { MachineDto, ResetDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { AttachmentPhoto } from '../../../components/meter/AttachmentPhoto';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { DecideResetDialog } from '../jobDetail/DecideResetDialog';
import { OWN_RESET_TEXT } from '../jobDetail/MeterResetsTab';
import { RESET_STATUS_OPTIONS, RESET_TONES } from '../shared/jobDisplay';
import { MachineFilter } from '../shared/financePickers';
import { PersonName } from '../shared/PersonName';
import { useMachineLabels } from '../shared/useMachineLabels';

/** Company-wide meter resets (pending by default) so an approver decides them without opening each machine. */
export function MeterResetsPage() {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const machineName = useMachineLabels();
  const { me } = useSession();
  const canDecide = useCanMutate(PERMISSIONS.tenantMeterApprove);
  const { focusId } = useParams();
  const [urlParams] = useSearchParams();
  const [status, setStatus] = useState(() =>
    focusId !== undefined
      ? ''
      : initialFilter(urlParams, 'status', RESET_STATUS_OPTIONS, 'PENDING'),
  );
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [deciding, setDeciding] = useState<ResetDto | null>(null);
  const machineId = machine?.id;
  const load = useCallback(
    (signal: AbortSignal) =>
      meterService.listResets({ status: status || undefined, machine_id: machineId }, signal),
    [status, machineId],
  );
  const resource = useAsyncResource(load);
  const loadFocused = useCallback(
    (id: string, signal: AbortSignal) => meterService.getReset(id, signal),
    [],
  );
  const focus = useRecordById<ResetDto>(loadFocused, focusId);
  const decideAction = (r: ResetDto) => {
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
  };
  const columns: DataColumn<ResetDto>[] = [
    { id: 'at', header: 'Effective', render: (r) => formatInstantIn(r.effective_at, timeZone) },
    { id: 'machine', header: 'Machine', render: (r) => machineName(r.machine_id) },
    {
      id: 'requester',
      header: 'Requested by',
      render: (r) => <PersonName userId={r.requested_by} />,
    },
    {
      id: 'reading',
      header: 'Reading (old → new)',
      align: 'right',
      render: (r) => `${r.old_reading} → ${r.new_reading}`,
    },
    { id: 'reason', header: 'Reason', render: (r) => r.reason },
    {
      id: 'evidence',
      header: 'Evidence',
      render: (r) =>
        r.evidence_attachment_id !== null ? (
          <AttachmentPhoto
            attachmentId={r.evidence_attachment_id}
            fetchUrl={(id) => meterService.attachmentUrl(id)}
            label="View evidence"
          />
        ) : (
          '—'
        ),
    },
    {
      id: 'status',
      header: 'Status',
      render: (r) => <StatusChip status={r.status} tones={RESET_TONES} />,
    },
    {
      id: 'decide',
      header: '',
      align: 'right',
      render: decideAction,
    },
  ];
  const focused = focusId === undefined ? null : focus.data;
  const focusMissing = focusId !== undefined && focus.error !== null;
  return (
    <>
      <PageHeader
        title="Meter resets"
        subtitle="Replaced or rolled-over hour meters across all machines, awaiting or after a decision"
      />
      {focused !== null && (
        <Alert severity="info" className="mb-3" action={decideAction(focused)}>
          {`The reset you opened: ${machineName(focused.machine_id)}, ${focused.old_reading} → ${focused.new_reading}, effective ${formatInstantIn(focused.effective_at, timeZone)}. Status: ${focused.status.toLowerCase()}.`}
        </Alert>
      )}
      <FocusMissingAlert missing={focusMissing} />
      <Stack spacing={2}>
        <Alert severity="info">
          Approving a reset re-bases later readings for that machine from its effective time. The
          person who requested a reset cannot decide it.
        </Alert>
        <Box className="flex flex-wrap items-center gap-3">
          <StaticSelectFilter
            label="Status"
            value={status}
            options={RESET_STATUS_OPTIONS}
            allLabel="All statuses"
            onChange={setStatus}
          />
          <Box sx={{ minWidth: 260 }}>
            <MachineFilter label="Machine" value={machine} onChange={setMachine} />
          </Box>
        </Box>
        <AsyncContent
          resource={resource}
          isEmpty={(d) => d.length === 0}
          emptyTitle={
            status === 'PENDING'
              ? 'No meter resets awaiting a decision'
              : 'No meter resets match these filters'
          }
          errorTitle="Could not load meter resets"
        >
          {(d) => (
            <StaticTable
              ariaLabel="Meter resets"
              columns={columns}
              rows={d}
              getRowId={(r) => r.id}
            />
          )}
        </AsyncContent>
      </Stack>
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
            if (focusId !== undefined) focus.reload();
          }}
        />
      )}
    </>
  );
}
