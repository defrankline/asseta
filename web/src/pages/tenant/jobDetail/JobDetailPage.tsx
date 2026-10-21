import ArrowBack from '@mui/icons-material/ArrowBack';
import { Box, Button, Paper, Stack, Tab, Tabs } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { jobService } from '../../../api/services/jobService';
import { machineService } from '../../../api/services/machineService';
import type { JobSummaryDto } from '../../../api/types';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { ROUTES } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { labelOf, machineLabel } from '../shared/display';
import { JOB_STATUS_OPTIONS } from '../shared/jobDisplay';
import { useJobSites } from '../shared/useJobSites';
import { AcknowledgementTab } from './AcknowledgementTab';
import { CapturesTab } from './CapturesTab';
import { JobActions } from './JobActions';
import { JobSummaryPanel } from './JobSummaryPanel';
import { MeterResetsTab } from './MeterResetsTab';
import { WorkLogTab } from './WorkLogTab';

type TabKey = 'readings' | 'worklog' | 'ack' | 'resets';

interface Loaded {
  summary: JobSummaryDto;
  machineName: string;
}

interface JobTabsProps {
  summary: JobSummaryDto;
  machineName: string;
  timeZone: string;
  onChanged: () => void;
}

function JobTabs({ summary, machineName, timeZone, onChanged }: JobTabsProps) {
  const { hasPermission } = useSession();
  const job = summary.job;
  const canMeterRead = hasPermission(PERMISSIONS.tenantMeterRead);
  const canResets =
    hasPermission(PERMISSIONS.tenantMeterCapture) || hasPermission(PERMISSIONS.tenantMeterApprove);
  const available: { key: TabKey; label: string }[] = [
    ...(canMeterRead ? [{ key: 'readings' as const, label: 'Readings & evidence' }] : []),
    { key: 'worklog', label: 'Work log' },
    { key: 'ack', label: 'Acknowledgement' },
    ...(canResets ? [{ key: 'resets' as const, label: 'Meter resets' }] : []),
  ];
  const [tab, setTab] = useState<TabKey | null>(null);
  const active = available.find((t) => t.key === tab)?.key ?? available[0]?.key ?? 'worklog';
  return (
    <Paper variant="outlined">
      <Tabs
        value={active}
        onChange={(_e, v: TabKey) => {
          setTab(v);
        }}
        variant="scrollable"
        aria-label="Job details"
      >
        {available.map((t) => (
          <Tab key={t.key} value={t.key} label={t.label} />
        ))}
      </Tabs>
      <Box className="p-3">
        {active === 'readings' && (
          <CapturesTab job={job} timeZone={timeZone} onChanged={onChanged} />
        )}
        {active === 'worklog' && <WorkLogTab job={job} timeZone={timeZone} onChanged={onChanged} />}
        {active === 'ack' && (
          <AcknowledgementTab
            job={job}
            suggestedHours={summary.billable_hours}
            timeZone={timeZone}
            onChanged={onChanged}
          />
        )}
        {active === 'resets' && (
          <MeterResetsTab
            machineId={job.machine_id}
            machineName={machineName}
            timeZone={timeZone}
          />
        )}
      </Box>
    </Paper>
  );
}

/** Job summary, lifecycle actions, readings & evidence, work log, acknowledgement and resets. */
export function JobDetailPage() {
  const { jobId = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const { hasPermission } = useSession();
  const { label: siteLabel } = useJobSites();
  const canMachines = hasPermission(PERMISSIONS.tenantMachineRead);
  const load = useCallback(
    async (signal: AbortSignal): Promise<Loaded> => {
      const summary = await jobService.summary(jobId, signal);
      let machineName = summary.job.machine_id;
      if (canMachines) {
        try {
          machineName = machineLabel(await machineService.get(summary.job.machine_id, signal));
        } catch {
          // Fall back to the id; the job itself loaded fine.
        }
      }
      return { summary, machineName };
    },
    [jobId, canMachines],
  );
  const resource = useAsyncResource(load);
  const job = resource.data?.summary.job ?? null;
  return (
    <>
      <PageHeader
        title={job === null ? 'Job' : `Job ${job.job_number}`}
        subtitle={job === null ? 'Job details' : labelOf(JOB_STATUS_OPTIONS, job.status)}
        actions={
          <>
            <Button component={RouterLink} to={ROUTES.tenantJobs} startIcon={<ArrowBack />}>
              All jobs
            </Button>
            {job !== null && (
              <JobActions
                job={job}
                onChanged={(j) => {
                  notify.success(
                    `Job ${j.job_number} is now ${labelOf(JOB_STATUS_OPTIONS, j.status)}.`,
                  );
                  resource.reload();
                }}
              />
            )}
          </>
        }
      />
      <AsyncContent
        resource={resource}
        errorTitle="Could not load the job"
        loadingLabel="Loading job"
      >
        {(d) => (
          <Stack spacing={3}>
            <JobSummaryPanel
              summary={d.summary}
              machineName={d.machineName}
              siteName={siteLabel(d.summary.job.job_site_id)}
              timeZone={timeZone}
              canSeeExceptions={hasPermission(PERMISSIONS.tenantMeterRead)}
            />
            <JobTabs
              summary={d.summary}
              machineName={d.machineName}
              timeZone={timeZone}
              onChanged={resource.reload}
            />
          </Stack>
        )}
      </AsyncContent>
    </>
  );
}
