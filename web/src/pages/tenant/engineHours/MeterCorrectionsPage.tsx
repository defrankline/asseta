import Add from '@mui/icons-material/Add';
import { Box, Button } from '@mui/material';
import { useCallback, useMemo, useRef, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { object, string, type ObjectSchema } from 'yup';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useMutationGuard } from '../../../access/useCanMutate';
import { engineHoursService } from '../../../api/services/engineHoursService';
import type { CorrectionDto, MachineDto, MeterCaptureDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import { FormDialog } from '../../../components/forms/FormDialog';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { DetailsDrawer } from '../../../components/lifecycle/DetailsDrawer';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { engineHoursMachinePath, jobDetailPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { FormikFieldMachineIdPicker } from '../field/fieldPickers';
import { machineLabel } from '../shared/display';
import { MachineFilter } from '../shared/financePickers';
import { optionId } from '../shared/lookups';
import { PersonName } from '../shared/PersonName';
import { DecideCorrectionDialog } from './DecideDialogs';
import {
  PROPOSAL_STATUS_LABELS,
  PROPOSAL_STATUS_OPTIONS,
  PROPOSAL_STATUS_TONES,
} from './engineHoursDisplay';
import { readingOptionLabel, searchMachineReadings } from './engineHoursLookups';
import { DecideButton } from './MeterDecisionDialog';
import { ProposeCorrectionDialog } from './ProposeCorrectionDialog';

const machineOf = (c: CorrectionDto) => c.machine_code ?? `${c.machine_id.slice(0, 8)}…`;

interface PickValues {
  machine_id: string;
  capture_id: string;
}

const pickSchema: ObjectSchema<PickValues> = object({
  machine_id: string().required('Choose the machine'),
  capture_id: string().required('Choose the reading to correct'),
});

interface Picked {
  capture: MeterCaptureDto;
  machineLabel: string;
}

/** A machine's live readings (server search), bound to the Formik `capture_id` field. */
function ReadingPicker({
  machineId,
  timeZone,
  onPicked,
}: {
  machineId: string;
  timeZone: string;
  onPicked: (c: MeterCaptureDto | null) => void;
}) {
  const search = useMemo(() => searchMachineReadings(machineId), [machineId]);
  const label = useCallback(
    (c: MeterCaptureDto) => readingOptionLabel(c, (iso) => formatInstantIn(iso, timeZone)),
    [timeZone],
  );
  return (
    <FormikAsyncIdAutocomplete<MeterCaptureDto>
      name="capture_id"
      label="Reading to correct"
      required
      fetchOptions={search}
      getOptionId={optionId}
      getOptionLabel={label}
      onOptionChange={onPicked}
      noOptionsText="No accepted readings for this machine"
    />
  );
}

/** Step 1 of a correction from this page: choose the machine and the live reading to correct. */
function PickReadingDialog({
  onClose,
  onPicked,
}: {
  onClose: () => void;
  onPicked: (p: Picked) => void;
}) {
  const timeZone = useDisplayTimeZone();
  const machine = useRef<MachineDto | null>(null);
  const capture = useRef<MeterCaptureDto | null>(null);
  return (
    <FormDialog<PickValues>
      open
      title="Propose a reading correction"
      initialValues={{ machine_id: '', capture_id: '' }}
      validationSchema={pickSchema}
      submitLabel="Continue"
      onClose={onClose}
      closeOnSuccess={false}
      onSubmit={async () => {
        const c = capture.current;
        if (c === null) return;
        onPicked({
          capture: c,
          machineLabel: machine.current === null ? '—' : machineLabel(machine.current),
        });
        await Promise.resolve();
      }}
    >
      {(formik) => (
        <>
          <FormikFieldMachineIdPicker
            name="machine_id"
            label="Machine"
            required
            onOptionChange={(m) => {
              machine.current = m;
            }}
          />
          {formik.values.machine_id !== '' && (
            <ReadingPicker
              key={formik.values.machine_id}
              machineId={formik.values.machine_id}
              timeZone={timeZone}
              onPicked={(c) => {
                capture.current = c;
              }}
            />
          )}
        </>
      )}
    </FormDialog>
  );
}

/** Reading corrections: proposals to supersede a reading, decided by a second person. */
export function MeterCorrectionsPage() {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const can = useMutationGuard();
  const canDecide = can(PERMISSIONS.tenantMeterApprove);
  const [status, setStatus] = useState('PROPOSED');
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [viewing, setViewing] = useState<CorrectionDto | null>(null);
  const [deciding, setDeciding] = useState<CorrectionDto | null>(null);
  const [picking, setPicking] = useState(false);
  const [picked, setPicked] = useState<Picked | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = () => {
    setReloadKey((k) => k + 1);
  };
  const fetchPage = useCallback<FetchPage<CorrectionDto>>(
    (query, signal) => engineHoursService.listCorrections(query, signal),
    [],
  );
  const decideAction = (c: CorrectionDto) =>
    canDecide && c.status === 'PROPOSED' ? (
      <DecideButton
        proposedBy={c.proposed_by}
        onClick={() => {
          setViewing(null);
          setDeciding(c);
        }}
      />
    ) : null;
  const columns: DataColumn<CorrectionDto>[] = [
    { id: 'at', header: 'Proposed', render: (c) => formatInstantIn(c.proposed_at, timeZone) },
    { id: 'machine', header: 'Machine', render: machineOf },
    {
      id: 'reading',
      header: 'Reading (old → new)',
      align: 'right',
      render: (c) => <span className="font-mono">{`${c.old_reading} → ${c.new_reading}`}</span>,
    },
    { id: 'reason', header: 'Reason', render: (c) => c.reason },
    { id: 'by', header: 'Proposed by', render: (c) => <PersonName userId={c.proposed_by} /> },
    {
      id: 'status',
      header: 'Status',
      render: (c) => (
        <StatusChip
          status={c.status}
          tones={PROPOSAL_STATUS_TONES}
          label={PROPOSAL_STATUS_LABELS[c.status]}
        />
      ),
    },
    { id: 'decide', header: '', align: 'right', render: decideAction },
  ];
  return (
    <>
      <PageHeader
        title="Reading corrections"
        subtitle="Corrected meter readings: the original stays on record; a second person approves"
        actions={
          can(PERMISSIONS.tenantMeterCapture) ? (
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setPicking(true);
              }}
            >
              Propose correction
            </Button>
          ) : undefined
        }
      />
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(c) => c.id}
        searchPlaceholder="Search machine or reason"
        reloadKey={reloadKey}
        filters={{ status: status || undefined, machine_id: machine?.id }}
        emptyTitle={status === 'PROPOSED' ? 'No corrections awaiting a decision' : 'No corrections'}
        isRowMuted={(c) => c.status === 'REJECTED'}
        onRowClick={setViewing}
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="Status"
              value={status}
              options={PROPOSAL_STATUS_OPTIONS}
              allLabel="All statuses"
              onChange={setStatus}
            />
            <Box sx={{ minWidth: 240 }}>
              <MachineFilter label="Machine" value={machine} onChange={setMachine} />
            </Box>
          </Box>
        }
      />
      {viewing !== null && (
        <DetailsDrawer
          title={`Correction · ${machineOf(viewing)}`}
          status={
            <StatusChip
              status={viewing.status}
              tones={PROPOSAL_STATUS_TONES}
              label={PROPOSAL_STATUS_LABELS[viewing.status]}
            />
          }
          actions={
            <Box className="flex flex-wrap gap-2">
              <Button component={RouterLink} to={engineHoursMachinePath(viewing.machine_id)}>
                Engine hours
              </Button>
              {viewing.job_id !== null && (
                <Button component={RouterLink} to={jobDetailPath(viewing.job_id)}>
                  Open job
                </Button>
              )}
              {decideAction(viewing)}
            </Box>
          }
          onClose={() => {
            setViewing(null);
          }}
        >
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Old reading', value: viewing.old_reading },
              { label: 'New reading', value: viewing.new_reading },
              { label: 'Reason', value: viewing.reason },
              { label: 'Job', value: viewing.job_id === null ? 'None (daily reading)' : 'Yes' },
              { label: 'Proposed by', value: <PersonName userId={viewing.proposed_by} /> },
              { label: 'Proposed', value: formatInstantIn(viewing.proposed_at, timeZone) },
              { label: 'Decided by', value: <PersonName userId={viewing.decided_by} /> },
              { label: 'Decided', value: formatInstantIn(viewing.decided_at, timeZone) },
              { label: 'Decision note', value: viewing.decision_note ?? '—' },
              { label: 'Policy', value: viewing.policy_version },
            ]}
          />
        </DetailsDrawer>
      )}
      {deciding !== null && (
        <DecideCorrectionDialog
          correction={deciding}
          timeZone={timeZone}
          onClose={() => {
            setDeciding(null);
          }}
          onDecided={(c) => {
            notify.success(`Correction ${PROPOSAL_STATUS_LABELS[c.status].toLowerCase()}.`);
            reload();
          }}
        />
      )}
      {picking && (
        <PickReadingDialog
          onClose={() => {
            setPicking(false);
          }}
          onPicked={(p) => {
            setPicking(false);
            setPicked(p);
          }}
        />
      )}
      {picked !== null && (
        <ProposeCorrectionDialog
          capture={picked.capture}
          machineLabel={picked.machineLabel}
          onClose={() => {
            setPicked(null);
          }}
          onProposed={(c) => {
            notify.success(
              c.status === 'APPROVED'
                ? 'Reading corrected.'
                : 'Correction proposed; a second person decides it.',
            );
            reload();
          }}
        />
      )}
    </>
  );
}
