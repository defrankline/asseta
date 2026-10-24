import { Alert, Box, Button, Chip, Link, Paper, Stack, Tooltip, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useMutationGuard } from '../../../access/useCanMutate';
import { engineHoursService } from '../../../api/services/engineHoursService';
import type {
  BaselineDto,
  IntervalDto,
  MachineEngineHoursDto,
  SegmentDto,
} from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { DateTimeField } from '../../../components/forms/DateTimeField';
import { DetailSection } from '../../../components/lifecycle/EntityDetailsLayout';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { jobDetailPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { PersonName } from '../shared/PersonName';
import { ProposeBaselineDialog, ProposeBaselineFromReadingDialog } from './BaselineDialogs';
import { ClassifyHoursDialog, type SegmentRef } from './ClassifyHoursDialog';
import {
  CLASSIFICATION_LABELS,
  CLASSIFICATION_TONES,
  hoursText,
  isOpenItem,
  OUTCOME_LABELS,
  PROPOSAL_STATUS_LABELS,
  PROPOSAL_STATUS_TONES,
  RECONCILIATION_LABELS,
  RECONCILIATION_TONES,
  REVIEW_LABELS,
  sourceLabel,
} from './engineHoursDisplay';
import { DecideBaselineDialog } from './DecideDialogs';
import { DecideButton } from './MeterDecisionDialog';

function SegmentChip({ segment }: { segment: SegmentDto }) {
  if (segment.kind === 'CUSTOMER_WORK') {
    const label = `Job ${segment.job_number ?? '—'} · ${hoursText(segment.hours)}`;
    return segment.job_id === null ? (
      <Chip size="small" color="success" label={label} />
    ) : (
      <Chip
        size="small"
        color="success"
        label={label}
        component={RouterLink}
        to={jobDetailPath(segment.job_id)}
        clickable
      />
    );
  }
  const pending =
    segment.proposal !== null ? ` · ${OUTCOME_LABELS[segment.proposal.outcome]} proposed` : '';
  return (
    <StatusChip
      status={segment.classification}
      tones={CLASSIFICATION_TONES}
      label={`${CLASSIFICATION_LABELS[segment.classification]} · ${hoursText(segment.hours)}${pending}`}
    />
  );
}

/** Proportional bar of an interval's segments (customer work vs unallocated), labelled for screen readers. */
function SegmentBar({ interval }: { interval: IntervalDto }) {
  const total = interval.segments.reduce((sum, s) => sum + Math.max(Number(s.hours), 0), 0);
  if (total <= 0) return null;
  return (
    <Box
      role="img"
      aria-label={interval.segments
        .map((s) => `${s.kind === 'CUSTOMER_WORK' ? 'customer work' : 'unallocated'} ${s.hours} h`)
        .join(', ')}
      sx={{
        display: 'flex',
        height: 6,
        borderRadius: 1,
        overflow: 'hidden',
        mt: 0.5,
        minWidth: 120,
      }}
    >
      {interval.segments.map((s, i) => (
        <Box
          key={i}
          sx={{
            flexGrow: Math.max(Number(s.hours), 0),
            bgcolor:
              s.kind === 'CUSTOMER_WORK'
                ? 'success.main'
                : s.classification === 'UNEXPLAINED'
                  ? 'warning.main'
                  : 'info.main',
          }}
        />
      ))}
    </Box>
  );
}

function BaselineSummary({ baseline, timeZone }: { baseline: BaselineDto; timeZone: string }) {
  return (
    <KeyValueGrid
      columns={4}
      items={[
        { label: 'Reading', value: hoursText(baseline.reading) },
        { label: 'Taken', value: formatInstantIn(baseline.captured_at, timeZone) },
        {
          label: 'Status',
          value: (
            <StatusChip
              status={baseline.status}
              tones={PROPOSAL_STATUS_TONES}
              label={PROPOSAL_STATUS_LABELS[baseline.status]}
            />
          ),
        },
        {
          label: 'Proposed by',
          value: <PersonName userId={baseline.proposed_by} />,
        },
        ...(baseline.decided_at !== null
          ? [
              { label: 'Approved by', value: <PersonName userId={baseline.decided_by} /> },
              { label: 'Approved', value: formatInstantIn(baseline.decided_at, timeZone) },
            ]
          : []),
        ...(baseline.note !== null ? [{ label: 'Note', value: baseline.note }] : []),
      ]}
    />
  );
}

type Dialog =
  | { kind: 'baseline' }
  | { kind: 'fromReading' }
  | { kind: 'decide'; baseline: BaselineDto }
  | { kind: 'classify'; segment: SegmentRef }
  | null;

interface LedgerViewProps {
  data: MachineEngineHoursDto;
  timeZone: string;
  onChanged: () => void;
}

function LedgerView({ data, timeZone, onChanged }: LedgerViewProps) {
  const notify = useNotify();
  const can = useMutationGuard();
  const [dialog, setDialog] = useState<Dialog>(null);
  const machine = { id: data.machine_id, label: `${data.machine_code} · ${data.machine_name}` };
  const canClassify = can(PERMISSIONS.tenantMeterReview);
  const columns: DataColumn<IntervalDto>[] = [
    {
      id: 'from',
      header: 'From',
      render: (i) => (
        <span>
          <span className="font-mono">{i.start.reading}</span> · {sourceLabel(i.start.source)}
          <br />
          <Typography variant="caption" color="text.secondary">
            {formatInstantIn(i.start.at, timeZone)}
          </Typography>
        </span>
      ),
    },
    {
      id: 'to',
      header: 'To',
      render: (i) => (
        <span>
          <span className="font-mono">{i.end.reading}</span> · {sourceLabel(i.end.source)}
          <br />
          <Typography variant="caption" color="text.secondary">
            {formatInstantIn(i.end.at, timeZone)}
          </Typography>
        </span>
      ),
    },
    {
      id: 'hours',
      header: 'Hours',
      align: 'right',
      render: (i) =>
        i.reset_applied ? (
          <Tooltip title={`Meter reset applied; raw difference ${i.raw_hours} h`}>
            <span className="font-mono">{i.hours}*</span>
          </Tooltip>
        ) : (
          <span className="font-mono">{i.hours}</span>
        ),
    },
    {
      id: 'breakdown',
      header: 'Breakdown',
      render: (i) => (
        <Box>
          <Box className="flex flex-wrap gap-1">
            {i.segments.map((s, idx) => (
              <SegmentChip key={idx} segment={s} />
            ))}
          </Box>
          <SegmentBar interval={i} />
        </Box>
      ),
    },
    {
      id: 'checks',
      header: 'Checks',
      render: (i) => (
        <Box className="flex flex-wrap gap-1">
          <StatusChip
            status={i.review}
            tones={{ VERIFIED: 'default', PENDING_REVIEW: 'info' }}
            label={REVIEW_LABELS[i.review]}
          />
          {i.inconsistent && <Chip size="small" color="warning" label="Readings inconsistent" />}
          {i.overlapping_job_ids.length > 0 && (
            <Chip size="small" color="warning" label="Overlapping jobs" />
          )}
        </Box>
      ),
    },
    {
      id: 'action',
      header: '',
      align: 'right',
      render: (i) => {
        const open = i.segments.find((s) => isOpenItem(i, s));
        if (!canClassify || open === undefined) return null;
        return (
          <Button
            size="small"
            onClick={() => {
              setDialog({
                kind: 'classify',
                segment: {
                  machineId: data.machine_id,
                  machineLabel: machine.label,
                  start: i.start,
                  end: i.end,
                  hours: open.hours,
                },
              });
            }}
          >
            Explain
          </Button>
        );
      },
    },
  ];
  const t = data.totals;
  const pending = data.baseline_proposal;
  return (
    <Stack spacing={3}>
      <DetailSection
        title="Baseline"
        actions={
          data.baseline === null && pending === null ? (
            <Box className="flex flex-wrap gap-2">
              {can(PERMISSIONS.tenantMeterCapture) && (
                <Button
                  variant="contained"
                  size="small"
                  onClick={() => {
                    setDialog({ kind: 'baseline' });
                  }}
                >
                  Propose baseline
                </Button>
              )}
              {can(PERMISSIONS.tenantMeterReview) && (
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => {
                    setDialog({ kind: 'fromReading' });
                  }}
                >
                  Use an existing reading
                </Button>
              )}
            </Box>
          ) : undefined
        }
      >
        {data.baseline !== null && <BaselineSummary baseline={data.baseline} timeZone={timeZone} />}
        {pending !== null && (
          <Stack spacing={1}>
            <Alert
              severity="info"
              action={
                can(PERMISSIONS.tenantMeterApprove) ? (
                  <DecideButton
                    proposedBy={pending.proposed_by}
                    onClick={() => {
                      setDialog({ kind: 'decide', baseline: pending });
                    }}
                  />
                ) : undefined
              }
            >
              A baseline proposal awaits a second person&apos;s decision.
            </Alert>
            <BaselineSummary baseline={pending} timeZone={timeZone} />
          </Stack>
        )}
        {data.baseline === null && pending === null && (
          <Alert severity="warning">
            No approved baseline yet: engine hours are reconciled from an approved starting reading.
          </Alert>
        )}
      </DetailSection>
      <DetailSection title="Totals">
        <KeyValueGrid
          columns={4}
          items={[
            { label: 'Engine hours', value: hoursText(t.total_hours) },
            { label: 'Customer work', value: hoursText(t.customer_work_hours) },
            { label: 'Unallocated', value: hoursText(t.unallocated_hours) },
            { label: 'Not yet explained', value: hoursText(t.unexplained_hours) },
            { label: 'Explanation proposed', value: hoursText(t.proposed_hours) },
            { label: 'Non-customer activity', value: hoursText(t.approved_non_customer_hours) },
            { label: 'Identified variance', value: hoursText(t.identified_variance_hours) },
            { label: 'Readings under review', value: hoursText(t.pending_review_hours) },
          ]}
        />
      </DetailSection>
      {data.overlaps.length > 0 && (
        <Alert severity="warning">
          {data.overlaps.length === 1
            ? 'Two jobs on this machine overlap'
            : `${String(data.overlaps.length)} job overlaps on this machine`}{' '}
          ({data.overlaps.map((o) => o.basis).join(', ')}). Hours are never counted twice; review
          the jobs concerned.
        </Alert>
      )}
      <DetailSection title="Engine-hour timeline">
        {data.intervals.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No intervals yet: the ledger starts at the approved baseline and grows with each
            reading.
          </Typography>
        ) : (
          <StaticTable
            ariaLabel="Engine-hour intervals"
            columns={columns}
            rows={data.intervals}
            getRowId={(i) => `${i.start.ref}:${i.end.ref}`}
          />
        )}
      </DetailSection>
      {dialog?.kind === 'baseline' && (
        <ProposeBaselineDialog
          machine={machine}
          onClose={() => {
            setDialog(null);
          }}
          onProposed={() => {
            notify.success('Baseline proposed; a second person decides it.');
            onChanged();
          }}
        />
      )}
      {dialog?.kind === 'fromReading' && (
        <ProposeBaselineFromReadingDialog
          machine={machine}
          onClose={() => {
            setDialog(null);
          }}
          onProposed={() => {
            notify.success('Baseline proposed; a second person decides it.');
            onChanged();
          }}
        />
      )}
      {dialog?.kind === 'decide' && (
        <DecideBaselineDialog
          baseline={dialog.baseline}
          timeZone={timeZone}
          onClose={() => {
            setDialog(null);
          }}
          onDecided={(b) => {
            notify.success(`Baseline ${PROPOSAL_STATUS_LABELS[b.status].toLowerCase()}.`);
            onChanged();
          }}
        />
      )}
      {dialog?.kind === 'classify' && (
        <ClassifyHoursDialog
          segment={dialog.segment}
          onClose={() => {
            setDialog(null);
          }}
          onProposed={(c) => {
            notify.success(
              c.status === 'APPROVED'
                ? 'Hours explained.'
                : 'Explanation proposed; a second person decides it.',
            );
            onChanged();
          }}
        />
      )}
    </Stack>
  );
}

interface MachineEngineHoursPanelProps {
  machineId: string;
}

/**
 * A machine's engine-hour ledger: baseline, totals and the interval timeline (each interval between
 * two consecutive readings split into customer work and unallocated hours). Derived on every load.
 */
export function MachineEngineHoursPanel({ machineId }: MachineEngineHoursPanelProps) {
  const timeZone = useDisplayTimeZone();
  const [from, setFrom] = useState<string | null>(null);
  const [to, setTo] = useState<string | null>(null);
  const load = useCallback(
    (signal: AbortSignal) =>
      engineHoursService.machine(
        machineId,
        { from: from ?? undefined, to: to ?? undefined },
        signal,
      ),
    [machineId, from, to],
  );
  const resource = useAsyncResource(load);
  return (
    <Stack spacing={2}>
      <Paper variant="outlined" className="flex flex-wrap items-center gap-3 p-3">
        <Box sx={{ minWidth: 220 }}>
          <DateTimeField label="From" value={from} onChange={setFrom} timezone={timeZone} />
        </Box>
        <Box sx={{ minWidth: 220 }}>
          <DateTimeField label="To" value={to} onChange={setTo} timezone={timeZone} />
        </Box>
        {resource.data !== null && (
          <StatusChip
            status={resource.data.status}
            tones={RECONCILIATION_TONES}
            label={RECONCILIATION_LABELS[resource.data.status]}
          />
        )}
        {resource.data !== null && (
          <Typography variant="caption" color="text.secondary">
            Policy {resource.data.policy_version}
          </Typography>
        )}
        {(from !== null || to !== null) && (
          <Link
            component="button"
            type="button"
            onClick={() => {
              setFrom(null);
              setTo(null);
            }}
          >
            Clear dates
          </Link>
        )}
      </Paper>
      <AsyncContent
        resource={resource}
        errorTitle="Could not load the engine-hour ledger"
        loadingLabel="Loading engine hours"
      >
        {(d) => <LedgerView data={d} timeZone={timeZone} onChanged={resource.reload} />}
      </AsyncContent>
    </Stack>
  );
}
