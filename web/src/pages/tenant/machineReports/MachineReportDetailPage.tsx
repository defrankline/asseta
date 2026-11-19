import { Alert, Link, Paper, Stack, Typography } from '@mui/material';
import { useCallback, useState, type ReactNode } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import type { MachineReportDto, MachineReportLineDto } from '../../../api/machineReportTypes';
import { machineReportService } from '../../../api/services/machineReportService';
import { meterService } from '../../../api/services/meterService';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import { EntityDetailsLayout } from '../../../components/lifecycle/EntityDetailsLayout';
import { LifecycleActionDialog } from '../../../components/lifecycle/LifecycleActionDialog';
import { EXCEPTION_TYPE_LABELS } from '../../../components/meter/exceptionText';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { hoursPurchasePath } from '../../../navigation/hoursRoutes';
import { ROUTES, machineReportPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { CaptureCard } from '../readings/CaptureCard';
import { machineText } from '../shared/names';
import {
  LINE_KIND_LABELS,
  REPORT_ERROR_HINTS,
  START_SOURCE_LABELS,
  hoursLabel,
  minus,
} from './machineReportDisplay';
import { ReportStatusChip } from './MachineReportParts';
import { useHoursPolicy } from '../hours/useHoursPolicy';
import { WhereText } from './VisitWhere';
import { formatVisitAt, formatVisitGap, visitGapFlagged, whereParts } from './visitDisplay';

type Open = 'approve' | 'reject' | null;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Paper variant="outlined" className="p-4">
      <Stack spacing={2}>
        <Typography variant="h6" component="h2">
          {title}
        </Typography>
        {children}
      </Stack>
    </Paper>
  );
}

function lineWho(l: MachineReportLineDto): string {
  return l.kind === 'CUSTOMER'
    ? (l.customer_name ?? l.customer_id ?? '—')
    : (l.reason_name ?? l.reason_code ?? '—');
}

/** Customer hours before → after this report (submitted reports: their available hours now). */
function beforeAfter(l: MachineReportLineDto): string {
  if (l.kind !== 'CUSTOMER' || l.available_hours == null) return '—';
  return `${hoursLabel(l.available_hours)} → ${hoursLabel(minus(l.available_hours, l.hours))} left`;
}

function LinesTable({ lines }: { lines: readonly MachineReportLineDto[] }) {
  return (
    <StaticTable<MachineReportLineDto>
      ariaLabel="Report lines"
      rows={lines}
      getRowId={(l) => l.id}
      columns={[
        { id: 'kind', header: 'Kind', render: (l) => LINE_KIND_LABELS[l.kind] },
        { id: 'who', header: 'Customer / reason', render: lineWho },
        { id: 'hours', header: 'Hours', align: 'right', render: (l) => hoursLabel(l.hours) },
        { id: 'left', header: 'Customer hours', render: beforeAfter },
        {
          id: 'note',
          header: 'Note / orders',
          render: (l) =>
            l.kind === 'NON_PRODUCTIVE' ? (
              (l.note ?? '—')
            ) : (l.lots ?? []).length === 0 ? (
              '—'
            ) : (
              <Stack>
                {(l.lots ?? []).map((lot) => (
                  <Link
                    key={lot.purchase_id}
                    component={RouterLink}
                    to={hoursPurchasePath(lot.purchase_id)}
                  >
                    {lot.purchase_number ?? 'Order'} · {hoursLabel(lot.hours)}
                  </Link>
                ))}
              </Stack>
            ),
        },
      ]}
    />
  );
}

function TrackerCheck({ report }: { report: MachineReportDto }) {
  const t = report.tracker;
  if (t == null || !t.available) {
    return (
      <Typography variant="body2" color="text.secondary">
        No tracker engine hours for this period.
      </Typography>
    );
  }
  return (
    <KeyValueGrid
      columns={3}
      items={[
        { label: 'Meter hours', value: hoursLabel(t.meter_hours) },
        {
          label: 'Tracker engine hours',
          value: t.tracker_hours === null ? '—' : hoursLabel(t.tracker_hours),
        },
        {
          label: 'Difference (meter − tracker)',
          value: t.difference === null ? '—' : hoursLabel(t.difference),
        },
      ]}
    />
  );
}

/** The reading behind the report: photo, GPS and evidence (when the user may read readings). */
function ReadingEvidence({ captureId, timeZone }: { captureId: string; timeZone: string }) {
  const load = useCallback(
    (signal: AbortSignal) => meterService.getCapture(captureId, signal),
    [captureId],
  );
  const res = useAsyncResource(load);
  return (
    <AsyncContent resource={res} errorTitle="Could not load the reading">
      {(c) => <CaptureCard capture={c} findings={[]} timeZone={timeZone} />}
    </AsyncContent>
  );
}

/**
 * Time since the machine's previous visit, where this report's reading was taken and where the previous
 * visit was (Owner/web show both places). Flagged in the warning colour over the company's setting.
 */
function VisitSection({
  report,
  warningHours,
  timeZone,
}: {
  report: MachineReportDto;
  warningHours: number | null;
  timeZone: string;
}) {
  const flagged = visitGapFlagged(report.since_previous_visit_seconds, warningHours);
  const here = {
    place: report.visit_place,
    site: report.visit_site_name,
    lat: report.visit_lat,
    lng: report.visit_lng,
    accuracy: report.visit_accuracy_m,
  };
  const before = {
    place: report.previous_visit_place,
    site: report.previous_visit_site_name,
    lat: report.previous_visit_lat,
    lng: report.previous_visit_lng,
    accuracy: report.previous_visit_accuracy_m,
  };
  const previousAt = report.previous_visit_at ?? null;
  return (
    <Stack spacing={0.5}>
      <Typography
        variant="body1"
        color={flagged ? 'warning.main' : 'text.primary'}
        sx={flagged ? { fontWeight: 600 } : undefined}
      >
        Since last visit: {formatVisitGap(report.since_previous_visit_seconds)}
      </Typography>
      {whereParts(here) !== null && (
        <Typography variant="body2">
          <WhereText place={here} />
        </Typography>
      )}
      {previousAt !== null && (
        <Typography variant="body2" color="text.secondary">
          Last visit: {formatVisitAt(previousAt, timeZone)}
          {whereParts(before) !== null && (
            <>
              {' · '}
              <WhereText place={before} />
            </>
          )}
        </Typography>
      )}
    </Stack>
  );
}

/** One machine report: readings and evidence, the split, tracker cross-check, decision. */
export function MachineReportDetailPage() {
  const { reportId = '' } = useParams();
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const { me, hasPermission } = useSession();
  const canDecide = useCanMutate(PERMISSIONS.tenantMachineReportApprove);
  const canReadReadings = hasPermission(PERMISSIONS.tenantMeterRead);
  const hours = useHoursPolicy();
  // The company's visit-gap warning (default 24 h while unknown; null = never flag).
  const warningHours = hours.policy === null ? 24 : hours.policy.visitGapWarningHours;
  const [open, setOpen] = useState<Open>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const load = useCallback(
    (signal: AbortSignal) => machineReportService.get(reportId, signal),
    [reportId],
  );
  const res = useAsyncResource(load, [reloadKey]);
  const r = res.data;
  const own = r !== null && me !== null && r.submitted_by === me.user_id;
  const pending = r?.status === 'SUBMITTED';
  const close = () => {
    setOpen(null);
  };
  const decided = (message: string) => {
    notify.success(message);
    setReloadKey((k) => k + 1);
  };
  return (
    <EntityDetailsLayout
      title={r === null ? 'Machine report' : r.report_number}
      subtitle={r === null ? undefined : machineText(r.machine_code, r.machine_name, r.machine_id)}
      back={{ label: 'All machine reports', to: ROUTES.tenantMachineReports }}
      {...(r !== null
        ? {
            status: <ReportStatusChip report={r} />,
            actions: (
              <ActionButtons
                primaryKey="approve"
                actions={[
                  {
                    key: 'approve',
                    label: 'Approve',
                    hidden: !canDecide || !pending || own,
                    onClick: () => {
                      setOpen('approve');
                    },
                  },
                  {
                    key: 'reject',
                    label: 'Reject',
                    destructive: true,
                    hidden: !canDecide || !pending || own,
                    onClick: () => {
                      setOpen('reject');
                    },
                  },
                ]}
              />
            ),
          }
        : {})}
    >
      <AsyncContent resource={res} errorTitle="Could not load the machine report">
        {(d) => (
          <Stack spacing={3}>
            {own && pending && canDecide && (
              <Alert severity="info">You submitted this report, so someone else decides it.</Alert>
            )}
            {d.status === 'REJECTED' && (
              <Alert severity="warning">
                Rejected{d.decided_by_name == null ? '' : ` by ${d.decided_by_name}`}
                {d.decision_note === null ? '.' : `: “${d.decision_note}”`}
                {d.corrected_by_id != null && (
                  <>
                    {' '}
                    Corrected by{' '}
                    <Link component={RouterLink} to={machineReportPath(d.corrected_by_id)}>
                      a later report
                    </Link>
                    .
                  </>
                )}
              </Alert>
            )}
            <Section title="Visit">
              <VisitSection report={d} warningHours={warningHours} timeZone={timeZone} />
            </Section>
            <Section title="Readings">
              <KeyValueGrid
                columns={3}
                items={[
                  {
                    label: 'Previous reading',
                    value: `${hoursLabel(d.start_reading)} · ${START_SOURCE_LABELS[d.start_source]}`,
                  },
                  { label: 'Previous at', value: formatInstantIn(d.start_at, timeZone) },
                  { label: 'New reading', value: hoursLabel(d.end_reading) },
                  { label: 'Read at', value: formatInstantIn(d.end_at, timeZone) },
                  { label: 'Hours', value: <strong>{hoursLabel(d.hours)}</strong> },
                  { label: 'Customer hours', value: hoursLabel(d.customer_hours) },
                  { label: 'Non-productive hours', value: hoursLabel(d.non_productive_hours) },
                  { label: 'Submitted by', value: d.submitted_by_name ?? '—' },
                  { label: 'Submitted at', value: formatInstantIn(d.submitted_at, timeZone) },
                  ...(d.decided_at === null
                    ? []
                    : [
                        { label: 'Decided by', value: d.decided_by_name ?? '—' },
                        { label: 'Decided at', value: formatInstantIn(d.decided_at, timeZone) },
                      ]),
                  ...(d.corrects_id === null
                    ? []
                    : [
                        {
                          label: 'Corrects',
                          value: (
                            <Link component={RouterLink} to={machineReportPath(d.corrects_id)}>
                              The rejected report
                            </Link>
                          ),
                        },
                      ]),
                  { label: 'Note', value: d.note ?? '—' },
                ]}
              />
            </Section>
            <Section title="Hours accounted for">
              <LinesTable lines={d.lines} />
            </Section>
            <Section title="Tracker cross-check">
              <TrackerCheck report={d} />
            </Section>
            {(d.findings ?? []).length > 0 && (
              <Section title="Reading findings">
                <Stack component="ul" sx={{ m: 0, pl: 3 }}>
                  {(d.findings ?? []).map((f, i) => (
                    <li key={`${f.type}-${String(i)}`}>
                      {EXCEPTION_TYPE_LABELS[f.type]}
                      {f.blocking ? ' (blocking)' : ''}
                    </li>
                  ))}
                </Stack>
              </Section>
            )}
            {canReadReadings && (
              <Section title="Reading evidence (photo and GPS)">
                <ReadingEvidence captureId={d.capture_id} timeZone={timeZone} />
              </Section>
            )}
          </Stack>
        )}
      </AsyncContent>
      {open === 'approve' && r !== null && (
        <LifecycleActionDialog<MachineReportDto>
          title={`Approve ${r.report_number}`}
          description={`${hoursLabel(r.customer_hours)} come off the customers' hours (oldest orders first) and ${hoursLabel(r.end_reading)} becomes the machine's last approved reading.`}
          confirmLabel="Approve"
          reason="optional"
          reasonLabel="Note"
          errorHints={REPORT_ERROR_HINTS}
          onConfirm={(note, key) =>
            machineReportService.approve(r.id, { note: note === '' ? null : note }, key)
          }
          onDone={() => {
            decided(`${r.report_number} approved.`);
          }}
          onClose={close}
        />
      )}
      {open === 'reject' && r !== null && (
        <LifecycleActionDialog<MachineReportDto>
          title={`Reject ${r.report_number}`}
          description="The supervisor is told your reason. A rejected report is kept as a record; the supervisor sends a new report with a new reading."
          confirmLabel="Reject"
          destructive
          reason="required"
          reasonLabel="Reason (the submitter sees it)"
          errorHints={REPORT_ERROR_HINTS}
          onConfirm={(reason, key) => machineReportService.reject(r.id, { reason }, key)}
          onDone={() => {
            decided('Report rejected. The supervisor will send a new report.');
          }}
          onClose={close}
        />
      )}
    </EntityDetailsLayout>
  );
}
