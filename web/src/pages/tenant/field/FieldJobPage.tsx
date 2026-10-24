import AddAPhoto from '@mui/icons-material/AddAPhoto';
import ArrowBack from '@mui/icons-material/ArrowBack';
import {
  Box,
  Button,
  Paper,
  Stack,
  Step,
  StepLabel,
  Stepper,
  Tab,
  Tabs,
  Typography,
} from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useMutationGuard } from '../../../access/useCanMutate';
import { jobService } from '../../../api/services/jobService';
import type { TransitionDef } from '../shared/jobDisplay';
import type {
  AcknowledgementDto,
  ActivityDto,
  CaptureResultDto,
  JobSummaryDto,
  ReadingKind,
} from '../../../api/types';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { ROUTES } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { ENTITY, entityKey } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';
import { useSession } from '../../../session/useSession';
import { formatDuration } from '../../../utils/time';
import { RecordExpenseDialog } from '../expenses/RecordExpenseDialog';
import { RecordFuelDialog } from '../expenses/FuelTab';
import { AcknowledgementDialog } from '../jobDetail/AcknowledgementDialog';
import { AcknowledgementTab } from '../jobDetail/AcknowledgementTab';
import { ActivityDialog } from '../jobDetail/ActivityDialog';
import { CapturesTab } from '../jobDetail/CapturesTab';
import { ConsoleCaptureDialog } from '../jobDetail/ConsoleCaptureDialog';
import { TransitionDialog } from '../jobDetail/JobActions';
import { JobSummaryPanel } from '../jobDetail/JobSummaryPanel';
import { MeterResetsTab } from '../jobDetail/MeterResetsTab';
import { WorkLogTab } from '../jobDetail/WorkLogTab';
import { labelOf } from '../shared/display';
import { ACTIVITY_TYPE_OPTIONS, JOB_STATUS_OPTIONS, JOB_TRANSITIONS } from '../shared/jobDisplay';
import { useJobSites } from '../shared/useJobSites';
import { CaptureResultPanel } from './CaptureResultPanel';
import { useFieldMachineLabels } from './fieldLookups';
import { JobCostsTab } from './JobCostsTab';
import {
  activeStepIndex,
  FIELD_STEPS,
  nextFieldStep,
  workTotals,
  type FieldStep,
} from './fieldWork';

type TabKey = 'readings' | 'worklog' | 'ack' | 'costs' | 'resets';
type Dialog =
  | { kind: 'reading'; reading: ReadingKind }
  | { kind: 'transition'; def: TransitionDef }
  | { kind: 'ack' }
  | { kind: 'activity' }
  | { kind: 'fuel' }
  | { kind: 'expense' };

interface Loaded {
  summary: JobSummaryDto;
  acks: AcknowledgementDto[];
  activities: ActivityDto[];
}

const STEP_TEXT: Readonly<Record<FieldStep, string>> = {
  OPENING:
    'Record the opening meter reading with a photo of the hour meter before work starts. The job can start once it is recorded.',
  START: 'The opening reading is recorded. Start the job when work begins.',
  CLOSING:
    'Log work, standby and downtime as it happens. When work ends, record the closing meter reading.',
  ACK: 'Record the customer representative’s acknowledgement: a signature on screen or their name.',
  COMPLETE: 'The closing reading and the customer acknowledgement are recorded. Complete the job.',
  DONE: 'This job is closed. Its readings, work log and acknowledgement are kept as recorded.',
  WAITING: 'This job is not approved yet; field work starts once the office approves it.',
};

function WorkTotalsLine({ activities }: { activities: readonly ActivityDto[] }) {
  const totals = workTotals(activities);
  const parts = (['WORK', 'STANDBY', 'DOWNTIME'] as const).map(
    (t) => `${labelOf(ACTIVITY_TYPE_OPTIONS, t)} ${formatDuration(totals.seconds[t])}`,
  );
  return (
    <Typography variant="body2" aria-label="Work log totals">
      {parts.join(' · ')}
      {totals.open > 0
        ? ` · ${String(totals.open)} open entr${totals.open === 1 ? 'y' : 'ies'}`
        : ''}
    </Typography>
  );
}

/**
 * Field work job workspace: the whole supervisor lifecycle from a browser — opening reading, start,
 * work log, closing reading, customer acknowledgement, complete — plus the job's evidence, costs
 * and meter resets. Every record is append-only; the server applies the capture policy.
 */
export function FieldJobPage() {
  const { jobId = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const { hasPermission } = useSession();
  const canMutate = useMutationGuard();
  const machineLabel = useFieldMachineLabels();
  const { label: siteLabel } = useJobSites();
  const [tab, setTab] = useState<TabKey>('readings');
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [lastResult, setLastResult] = useState<CaptureResultDto | null>(null);
  // Bumped after an action from the step card so the open tab reloads its list.
  const [tick, setTick] = useState(0);
  const load = useCallback(
    async (signal: AbortSignal): Promise<Loaded> => {
      const [summary, acks, activities] = await Promise.all([
        jobService.summary(jobId, signal),
        jobService.listAcknowledgements(jobId, signal),
        jobService.listActivities(jobId, signal),
      ]);
      return { summary, acks, activities };
    },
    [jobId],
  );
  const resource = useAsyncResource(load);
  useLiveRefresh(
    [entityKey(ENTITY.job, jobId), ENTITY.meterCapture, ENTITY.meterException],
    resource.reload,
  );
  const changed = () => {
    resource.reload();
    setTick((t) => t + 1);
  };
  const close = () => {
    setDialog(null);
  };
  const job = resource.data?.summary.job ?? null;
  const canCapture = canMutate(PERMISSIONS.tenantMeterCapture);
  const canLog = canMutate(PERMISSIONS.tenantJobLog);
  const canSpend = canMutate(PERMISSIONS.tenantExpenseWrite);
  const working = job !== null && (job.status === 'APPROVED' || job.status === 'IN_PROGRESS');

  const stepAction = (step: FieldStep) => {
    const open = (d: Dialog) => () => {
      setDialog(d);
    };
    switch (step) {
      case 'OPENING':
      case 'CLOSING':
        return canCapture ? (
          <Button
            variant="contained"
            startIcon={<AddAPhoto />}
            onClick={open({ kind: 'reading', reading: step })}
          >
            Record {step === 'OPENING' ? 'opening' : 'closing'} reading
          </Button>
        ) : null;
      case 'START':
      case 'COMPLETE': {
        const def = JOB_TRANSITIONS.find((t) => t.action === step);
        return canLog && def !== undefined ? (
          <Button variant="contained" onClick={open({ kind: 'transition', def })}>
            {def.label}
          </Button>
        ) : null;
      }
      case 'ACK':
        return canLog ? (
          <Button variant="contained" onClick={open({ kind: 'ack' })}>
            Record customer acknowledgement
          </Button>
        ) : null;
      default:
        return null;
    }
  };

  return (
    <>
      <PageHeader
        title={job === null ? 'Job' : `Job ${job.job_number}`}
        subtitle={
          job === null
            ? 'Field work'
            : `${labelOf(JOB_STATUS_OPTIONS, job.status)} · ${machineLabel(job.machine_id)}`
        }
        actions={
          <Button component={RouterLink} to={ROUTES.fieldJobs} startIcon={<ArrowBack />}>
            My jobs
          </Button>
        }
      />
      <AsyncContent
        resource={resource}
        errorTitle="Could not load the job"
        loadingLabel="Loading job"
      >
        {(d) => {
          const j = d.summary.job;
          const step = nextFieldStep({
            status: j.status,
            hasOpening: d.summary.opening_reading !== null,
            hasClosing: d.summary.closing_reading !== null,
            hasAcknowledgement: d.acks.length > 0,
          });
          return (
            <Stack spacing={3}>
              <Paper variant="outlined" className="p-4" component="section" aria-label="Next step">
                <Stack spacing={2}>
                  <Stepper activeStep={activeStepIndex(step)} alternativeLabel>
                    {FIELD_STEPS.map((s) => (
                      <Step key={s.label}>
                        <StepLabel>{s.label}</StepLabel>
                      </Step>
                    ))}
                  </Stepper>
                  <Typography variant="body1">{STEP_TEXT[step]}</Typography>
                  <Box className="flex flex-wrap items-center gap-2">
                    {stepAction(step)}
                    {working && canLog && (
                      <Button
                        variant="outlined"
                        onClick={() => {
                          setDialog({ kind: 'activity' });
                        }}
                      >
                        Log work
                      </Button>
                    )}
                    {working && canSpend && (
                      <>
                        <Button
                          variant="outlined"
                          onClick={() => {
                            setDialog({ kind: 'fuel' });
                          }}
                        >
                          Record fuel
                        </Button>
                        <Button
                          variant="outlined"
                          onClick={() => {
                            setDialog({ kind: 'expense' });
                          }}
                        >
                          Record expense
                        </Button>
                      </>
                    )}
                  </Box>
                  {d.activities.length > 0 && <WorkTotalsLine activities={d.activities} />}
                  {lastResult !== null && (
                    <CaptureResultPanel
                      result={lastResult}
                      onDismiss={() => {
                        setLastResult(null);
                      }}
                    />
                  )}
                </Stack>
              </Paper>
              <JobSummaryPanel
                summary={d.summary}
                machineName={machineLabel(j.machine_id)}
                siteName={siteLabel(j.job_site_id)}
                timeZone={timeZone}
                canSeeExceptions={hasPermission(PERMISSIONS.tenantMeterRead)}
              />
              <Paper variant="outlined">
                <Tabs
                  value={tab}
                  onChange={(_e, v: TabKey) => {
                    setTab(v);
                  }}
                  variant="scrollable"
                  aria-label="Job records"
                >
                  <Tab value="readings" label="Readings & evidence" />
                  <Tab value="worklog" label="Work log" />
                  <Tab value="ack" label="Acknowledgement" />
                  <Tab value="costs" label="Expenses & fuel" />
                  <Tab value="resets" label="Meter resets" />
                </Tabs>
                <Box className="p-3" key={`${tab}-${String(tick)}`}>
                  {tab === 'readings' && (
                    <CapturesTab
                      job={j}
                      timeZone={timeZone}
                      onChanged={resource.reload}
                      allowRecord={false}
                    />
                  )}
                  {tab === 'worklog' && (
                    <WorkLogTab job={j} timeZone={timeZone} onChanged={resource.reload} />
                  )}
                  {tab === 'ack' && (
                    <AcknowledgementTab
                      job={j}
                      suggestedHours={d.summary.billable_hours}
                      timeZone={timeZone}
                      onChanged={resource.reload}
                    />
                  )}
                  {tab === 'costs' && <JobCostsTab job={j} timeZone={timeZone} />}
                  {tab === 'resets' && (
                    <MeterResetsTab
                      machineId={j.machine_id}
                      machineName={machineLabel(j.machine_id)}
                      timeZone={timeZone}
                    />
                  )}
                </Box>
              </Paper>
            </Stack>
          );
        }}
      </AsyncContent>
      {job !== null && dialog?.kind === 'reading' && (
        <ConsoleCaptureDialog
          job={job}
          kind={dialog.reading}
          variant="field"
          onClose={close}
          onRecorded={(r) => {
            setLastResult(r);
            setTab('readings');
            changed();
          }}
        />
      )}
      {job !== null && dialog?.kind === 'transition' && (
        <TransitionDialog
          job={job}
          def={dialog.def}
          onClose={close}
          onDone={(updated) => {
            notify.success(
              `Job ${updated.job_number} is now ${labelOf(JOB_STATUS_OPTIONS, updated.status)}.`,
            );
            changed();
          }}
        />
      )}
      {job !== null && dialog?.kind === 'ack' && resource.data !== null && (
        <AcknowledgementDialog
          job={job}
          suggestedHours={resource.data.summary.billable_hours}
          timeZone={timeZone}
          onClose={close}
          onRecorded={() => {
            notify.success('Customer acknowledgement recorded.');
            setTab('ack');
            changed();
          }}
        />
      )}
      {job !== null && dialog?.kind === 'activity' && (
        <ActivityDialog
          job={job}
          timeZone={timeZone}
          onClose={close}
          onLogged={() => {
            notify.success('Activity logged.');
            setTab('worklog');
            changed();
          }}
        />
      )}
      {job !== null && dialog?.kind === 'fuel' && (
        <RecordFuelDialog
          variant="field"
          job={job}
          timeZone={timeZone}
          onClose={close}
          onRecorded={() => {
            notify.success('Fuel event recorded.');
            setTab('costs');
            changed();
          }}
        />
      )}
      {job !== null && dialog?.kind === 'expense' && (
        <RecordExpenseDialog
          variant="field"
          jobId={job.id}
          timeZone={timeZone}
          onClose={close}
          onRecorded={(e) => {
            notify.success(
              e.status === 'APPROVED'
                ? 'Expense recorded and auto-approved under the policy limit.'
                : 'Expense recorded; it is waiting for approval.',
            );
            setTab('costs');
            changed();
          }}
        />
      )}
    </>
  );
}
