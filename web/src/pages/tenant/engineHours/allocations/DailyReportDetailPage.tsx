import { Alert, Link, Typography } from '@mui/material';
import { useState } from 'react';
import { Link as RouterLink, useNavigate, useParams } from 'react-router';
import { mixed, object, string, type ObjectSchema } from 'yup';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useCanMutate } from '../../../../access/useCanMutate';
import type {
  DailyReportDto,
  DailyReportReviewIn,
  ReportAllocationDto,
  UnbillableLineDto,
} from '../../../../api/allocationTypes';
import { allocationService } from '../../../../api/services/allocationService';
import type { DataColumn } from '../../../../components/data/ServerDataTable';
import { StaticTable } from '../../../../components/data/StaticTable';
import { FormDialog } from '../../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { DetailSection } from '../../../../components/lifecycle/EntityDetailsLayout';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { recordPath } from '../../../../navigation/recordRoutes';
import { ROUTES } from '../../../../navigation/routes';
import { useNotify } from '../../../../notifications/useNotify';
import { useSession } from '../../../../session/useSession';
import { formatDate } from '../../../../utils/dates';
import { formatInstantIn } from '../../../../utils/time';
import { withErrorCode } from '../../shared/errorHints';
import { machineText } from '../../shared/names';
import { PersonName } from '../../shared/PersonName';
import { RecordDetail } from '../../shared/RecordDetail';
import { useRecordById } from '../../shared/useRecordById';
import { ENGINE_HOURS_ERROR_HINTS, hoursText, OWN_PROPOSAL_TEXT } from '../engineHoursDisplay';
import { allocationTarget, isNonZero } from './allocationDisplay';
import { KindChip } from './allocationKit';
import { ReportChips } from './dailyReportKit';
import { EvidenceList } from './EvidenceUpload';
import { SubmitDailyReportDialog } from './SubmitDailyReportDialog';

type Decision = DailyReportReviewIn['decision'];

interface ReviewValues {
  decision: Decision | '';
  note: string;
}

const reviewSchema: ObjectSchema<ReviewValues> = object({
  decision: mixed<Decision | ''>()
    .oneOf(['REVIEWED', 'RETURNED'], 'Choose an outcome')
    .required('Choose an outcome'),
  note: string()
    .trim()
    .required('A note is required')
    .min(5, 'At least 5 characters')
    .max(2000, 'At most 2000 characters'),
});

const DECISIONS = [
  { value: 'REVIEWED', label: 'Reviewed' },
  { value: 'RETURNED', label: 'Returned to the submitter' },
];

function ReviewDialog({
  report,
  onClose,
  onDone,
}: {
  report: DailyReportDto;
  onClose: () => void;
  onDone: (r: DailyReportDto) => void;
}) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<ReviewValues>
      open
      title={`Review the report of ${formatDate(report.report_date)}`}
      initialValues={{ decision: '', note: '' }}
      validationSchema={reviewSchema}
      submitLabel="Record review"
      onClose={onClose}
      onSubmit={async (v) => {
        const body: DailyReportReviewIn = {
          decision: v.decision === 'RETURNED' ? 'RETURNED' : 'REVIEWED',
          note: v.note.trim(),
        };
        try {
          onDone(await allocationService.reviewReport(report.id, body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, ENGINE_HOURS_ERROR_HINTS);
        }
      }}
    >
      <Alert severity="info">A returned report goes back to its submitter to be replaced.</Alert>
      <FormikSelectField name="decision" label="Outcome" options={DECISIONS} required />
      <FormikTextField
        name="note"
        label="Note"
        required
        multiline
        minRows={2}
        helperText="Kept on the record for audit (at least 5 characters)."
      />
    </FormDialog>
  );
}

const load = (id: string, signal: AbortSignal) => allocationService.getReport(id, signal);

const allocationColumns: DataColumn<ReportAllocationDto>[] = [
  {
    id: 'range',
    header: 'Readings',
    render: (a) => (
      <span className="font-mono">
        {a.start_reading} → {a.end_reading}
      </span>
    ),
  },
  {
    id: 'hours',
    header: 'Hours',
    align: 'right',
    render: (a) => <span className="font-mono">{a.hours}</span>,
  },
  { id: 'kind', header: 'Kind', render: (a) => <KindChip kind={a.kind} /> },
  { id: 'for', header: 'For', render: allocationTarget },
];

const unbillableColumns: DataColumn<UnbillableLineDto>[] = [
  { id: 'reason', header: 'Reason', render: (u) => u.reason_name ?? '—' },
  {
    id: 'hours',
    header: 'Hours',
    align: 'right',
    render: (u) => <span className="font-mono">{u.hours}</span>,
  },
];

/** One daily report (exact-record link): hours, reasons, allocations, evidence, review. */
export function DailyReportDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const navigate = useNavigate();
  const { me } = useSession();
  const res = useRecordById(load, id);
  const canReview = useCanMutate(PERMISSIONS.tenantMeterReview);
  const canSubmit = useCanMutate(PERMISSIONS.tenantMeterCapture);
  const [dialog, setDialog] = useState<'review' | 'replace' | null>(null);
  const close = () => {
    setDialog(null);
  };
  return (
    <>
      <RecordDetail
        resource={res}
        what="daily report"
        back={{ label: 'Daily reports', to: ROUTES.tenantDailyReports }}
        timeZone={timeZone}
        title={(r) =>
          `Daily report · ${machineText(r.machine_code, r.machine_name, r.machine_id)} · ${formatDate(r.report_date)}`
        }
        status={(r) => <ReportChips report={r} />}
        actions={(r) => [
          {
            key: 'review',
            label: 'Review',
            hidden: !canReview || r.status !== 'SUBMITTED',
            disabled: me !== null && r.submitted_by === me.user_id,
            disabledReason: OWN_PROPOSAL_TEXT,
            onClick: () => {
              setDialog('review');
            },
          },
          {
            key: 'replace',
            label: 'Submit a replacement',
            hidden: !canSubmit || (r.status !== 'SUBMITTED' && r.status !== 'RETURNED'),
            onClick: () => {
              setDialog('replace');
            },
          },
        ]}
        primaryKey="review"
        items={(r) => [
          { label: 'Opening reading', value: r.opening_reading },
          { label: 'Closing reading', value: r.closing_reading },
          { label: 'Total operating hours', value: hoursText(r.total_hours) },
          { label: 'Billable hours', value: hoursText(r.billable_hours) },
          { label: 'Unbillable hours', value: hoursText(r.unbillable_hours) },
          {
            label: 'Difference',
            value: isNonZero(r.difference_hours) ? (
              <Typography component="span" color="error" sx={{ fontWeight: 600 }}>
                {hoursText(r.difference_hours)}
              </Typography>
            ) : (
              'None'
            ),
          },
          {
            label: 'Submitted by',
            value: <PersonName userId={r.submitted_by} name={r.submitted_by_name} />,
          },
          { label: 'Created on device', value: formatInstantIn(r.client_created_at, timeZone) },
          { label: 'Note', value: r.note ?? '—' },
          {
            label: 'Repeat of',
            value:
              r.duplicate_of_id === null ? (
                '—'
              ) : (
                <Link component={RouterLink} to={recordPath('DAILY_REPORT', r.duplicate_of_id)}>
                  Open the first report
                </Link>
              ),
          },
          {
            label: 'Replaces',
            value:
              r.supersedes_id === null ? (
                '—'
              ) : (
                <Link component={RouterLink} to={recordPath('DAILY_REPORT', r.supersedes_id)}>
                  Open the earlier report
                </Link>
              ),
          },
          { label: 'Policy', value: r.policy_version },
        ]}
        history={(r) => [
          {
            key: 'submitted',
            at: r.submitted_at,
            label: 'Submitted',
            by: <PersonName userId={r.submitted_by} name={r.submitted_by_name} />,
            note: r.note,
          },
          {
            key: 'reviewed',
            at: r.reviewed_at,
            label: r.status === 'RETURNED' ? 'Returned' : 'Reviewed',
            by: <PersonName userId={r.reviewed_by} name={r.reviewed_by_name} />,
            note: r.review_note,
          },
        ]}
      >
        {(r) => (
          <>
            <DetailSection title="Unbillable hours by reason">
              {r.unbillable.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  None declared.
                </Typography>
              ) : (
                <StaticTable
                  ariaLabel="Unbillable hours"
                  columns={unbillableColumns}
                  rows={r.unbillable}
                  getRowId={(u) => u.reason_id}
                />
              )}
            </DetailSection>
            <DetailSection title="Allocations">
              {r.allocations.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No allocations for this day.
                </Typography>
              ) : (
                <StaticTable
                  ariaLabel="Allocations"
                  columns={allocationColumns}
                  rows={r.allocations}
                  getRowId={(a) => a.allocation_id}
                  onRowClick={(a) => {
                    void navigate(recordPath('WORK_ALLOCATION', a.allocation_id));
                  }}
                />
              )}
            </DetailSection>
            <DetailSection title="Evidence">
              <EvidenceList ids={r.evidence_attachment_ids} />
            </DetailSection>
          </>
        )}
      </RecordDetail>
      {dialog === 'review' && res.data !== null && (
        <ReviewDialog
          report={res.data}
          onClose={close}
          onDone={() => {
            notify.success('Review recorded.');
            res.reload();
          }}
        />
      )}
      {dialog === 'replace' && res.data !== null && (
        <SubmitDailyReportDialog
          replaces={res.data}
          onClose={close}
          onSubmitted={(r) => {
            notify.success('Replacement submitted.');
            void navigate(recordPath('DAILY_REPORT', r.id));
          }}
        />
      )}
    </>
  );
}
