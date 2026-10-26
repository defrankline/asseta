import { Alert, Box, Button, Paper, Tab, Tabs } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { revenueService } from '../../../api/services/revenueService';
import type { MachineDto, NonRevenueActivityDto, NonRevenueApprovalDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { recordPath } from '../../../navigation/recordRoutes';
import { jobDetailPath } from '../../../navigation/routes';
import { formatInstantIn } from '../../../utils/time';
import { MachineFilter } from '../shared/financePickers';
import { PersonName } from '../shared/PersonName';
import {
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_OPTIONS,
  ACTIVITY_STATUS_TONES,
  activityTypeLabel,
  APPROVAL_STATUS_OPTIONS,
} from './revenueDisplay';
import { differenceMachine } from './revenueDisplay';
import { approvalChip, useApprovalKit, useExplainActivity } from './revenueKits';

type TabKey = 'activities' | 'approvals';

function ActivitiesTab({ timeZone }: { timeZone: string }) {
  const navigate = useNavigate();
  const [status, setStatus] = useState('NONE');
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const explain = useExplainActivity(() => {
    setReloadKey((k) => k + 1);
  });
  const fetchPage = useCallback<FetchPage<NonRevenueActivityDto>>(
    (query, signal) => revenueService.listActivities(query, signal),
    [],
  );
  const columns: DataColumn<NonRevenueActivityDto>[] = [
    { id: 'machine', header: 'Machine', render: differenceMachine },
    { id: 'job', header: 'Job', render: (a) => a.job_number ?? '—' },
    { id: 'type', header: 'Type', render: (a) => activityTypeLabel(a.activity_type) },
    {
      id: 'when',
      header: 'When',
      render: (a) =>
        `${formatInstantIn(a.started_at, timeZone)} → ${formatInstantIn(a.ended_at, timeZone)}`,
    },
    {
      id: 'hours',
      header: 'Hours',
      align: 'right',
      render: (a) => <span className="font-mono">{a.hours}</span>,
    },
    {
      id: 'status',
      header: 'Status',
      render: (a) => (
        <StatusChip
          status={a.approval_status}
          tones={ACTIVITY_STATUS_TONES}
          label={ACTIVITY_STATUS_LABELS[a.approval_status]}
        />
      ),
    },
    {
      id: 'action',
      header: '',
      align: 'right',
      render: (a) =>
        explain.canExplain(a) ? (
          <Button
            size="small"
            onClick={(e) => {
              e.stopPropagation();
              explain.open(a);
            }}
          >
            Explain
          </Button>
        ) : (
          <RowActionsMenu
            label={`${activityTypeLabel(a.activity_type)} of ${a.job_number ?? 'job'}`}
            actions={[
              {
                key: 'approval',
                label: 'Open explanation',
                hidden: a.approval_id === null,
                onClick: () => {
                  if (a.approval_id !== null)
                    void navigate(recordPath('NON_REVENUE_APPROVAL', a.approval_id));
                },
              },
              {
                key: 'job',
                label: 'Open job',
                onClick: () => {
                  void navigate(jobDetailPath(a.job_id));
                },
              },
            ]}
          />
        ),
    },
  ];
  return (
    <>
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(a) => a.activity_id}
        searchable={false}
        reloadKey={reloadKey}
        filters={{ status: status || undefined, machine_id: machine?.id }}
        emptyTitle={status === 'NONE' ? 'Nothing awaiting explanation' : 'No non-revenue time'}
        onRowClick={(a) => {
          void navigate(
            a.approval_id === null
              ? jobDetailPath(a.job_id)
              : recordPath('NON_REVENUE_APPROVAL', a.approval_id),
          );
        }}
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="Status"
              value={status}
              options={ACTIVITY_STATUS_OPTIONS}
              allLabel="All statuses"
              onChange={setStatus}
            />
            <Box sx={{ minWidth: 240 }}>
              <MachineFilter label="Machine" value={machine} onChange={setMachine} />
            </Box>
          </Box>
        }
      />
      {explain.dialog}
    </>
  );
}

function ApprovalsTab({ timeZone }: { timeZone: string }) {
  const navigate = useNavigate();
  const [status, setStatus] = useState('PROPOSED');
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const kit = useApprovalKit(() => {
    setReloadKey((k) => k + 1);
  });
  const fetchPage = useCallback<FetchPage<NonRevenueApprovalDto>>(
    (query, signal) => revenueService.listApprovals(query, signal),
    [],
  );
  const open = (a: NonRevenueApprovalDto) => {
    void navigate(recordPath('NON_REVENUE_APPROVAL', a.id));
  };
  const columns: DataColumn<NonRevenueApprovalDto>[] = [
    { id: 'machine', header: 'Machine', render: differenceMachine },
    { id: 'job', header: 'Job', render: (a) => a.job_number ?? '—' },
    { id: 'type', header: 'Type', render: (a) => activityTypeLabel(a.activity_type) },
    {
      id: 'when',
      header: 'When',
      render: (a) =>
        `${formatInstantIn(a.started_at, timeZone)} → ${formatInstantIn(a.ended_at, timeZone)}`,
    },
    {
      id: 'hours',
      header: 'Hours',
      align: 'right',
      render: (a) => <span className="font-mono">{a.hours}</span>,
    },
    { id: 'reason', header: 'Reason', render: (a) => a.reason_name ?? '—' },
    {
      id: 'by',
      header: 'Explained by',
      render: (a) => <PersonName userId={a.proposed_by} name={a.proposed_by_name} />,
    },
    { id: 'status', header: 'Status', render: approvalChip },
    { id: 'decide', header: '', align: 'right', render: kit.decideCell },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (a) => (
        <RowActionsMenu
          label={`explanation of ${a.hours} h`}
          actions={[
            {
              key: 'view',
              label: 'View details',
              onClick: () => {
                open(a);
              },
            },
          ]}
        />
      ),
    },
  ];
  return (
    <>
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(a) => a.id}
        searchPlaceholder="Search machine or job"
        reloadKey={reloadKey}
        filters={{ status: status || undefined, machine_id: machine?.id }}
        emptyTitle={status === 'PROPOSED' ? 'No explanations awaiting a decision' : 'No approvals'}
        isRowMuted={(a) => a.status === 'REJECTED'}
        onRowClick={open}
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="Status"
              value={status}
              options={APPROVAL_STATUS_OPTIONS}
              allLabel="All statuses"
              onChange={setStatus}
            />
            <Box sx={{ minWidth: 240 }}>
              <MachineFilter label="Machine" value={machine} onChange={setMachine} />
            </Box>
          </Box>
        }
      />
      {kit.dialog}
    </>
  );
}

/**
 * Non-revenue time inside jobs (e.g. movement to or from a site): it counts as revenue until one
 * person explains it and another approves it.
 */
export function NonRevenuePage() {
  const timeZone = useDisplayTimeZone();
  const [params, setParams] = useSearchParams();
  const tab: TabKey = params.get('tab') === 'approvals' ? 'approvals' : 'activities';
  return (
    <>
      <PageHeader
        title="Non-revenue hours"
        subtitle="Time inside jobs that is not customer work, explained by one person and approved by another"
      />
      <Alert severity="info" sx={{ mb: 2 }}>
        Until approved, this time counts as customer work and expected revenue.
      </Alert>
      <Paper variant="outlined" sx={{ mb: 2 }}>
        <Tabs
          value={tab}
          aria-label="Non-revenue hours"
          onChange={(_e, v: TabKey) => {
            setParams({ tab: v });
          }}
        >
          <Tab value="activities" label="To explain" />
          <Tab value="approvals" label="Approvals" />
        </Tabs>
      </Paper>
      {tab === 'activities' ? (
        <ActivitiesTab timeZone={timeZone} />
      ) : (
        <ApprovalsTab timeZone={timeZone} />
      )}
    </>
  );
}
