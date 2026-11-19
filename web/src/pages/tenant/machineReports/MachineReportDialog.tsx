import {
  Alert,
  Button,
  Link,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Typography,
} from '@mui/material';
import { useFormikContext } from 'formik';
import { useCallback, useMemo, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { newUuid } from '../../../api/ids';
import type {
  AvailableHoursDto,
  MachineReportContextDto,
  MachineReportDto,
} from '../../../api/machineReportTypes';
import { machineReportService } from '../../../api/services/machineReportService';
import type { AttachmentDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { StepperFormDialog } from '../../../components/forms/StepperFormDialog';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { ROUTES } from '../../../navigation/routes';
import { compareDecimal, isDecimalString } from '../../../utils/money';
import { formatInstantIn } from '../../../utils/time';
import { CaptureEvidenceFields } from '../readings/ReadingEvidence';
import { gpsPendingError, useBrowserGps } from '../readings/readingEvidenceKit';
import { withErrorCode } from '../shared/errorHints';
import { REPORT_ERROR_HINTS, START_SOURCE_LABELS, hoursLabel } from './machineReportDisplay';
import { ReportLinesStep } from './ReportLinesStep';
import { ReportReview } from './ReportReview';
import { VisitWhere } from './VisitWhere';
import { formatVisitAt, formatVisitGap, secondsBetween } from './visitDisplay';
import {
  emptyReportValues,
  lineFieldsFor,
  meterDifference,
  READING_FIELDS,
  reportSchema,
  toReportPayload,
  type ReportRules,
  type ReportValues,
} from './reportForm';

interface ReadingStepProps {
  context: MachineReportContextDto;
  rules: ReportRules;
  /** When this reading is taken (the gap since the last visit counts to it). */
  capturedAt: string;
  photo: AttachmentDto | null;
  onPhotoChange: (photo: AttachmentDto | null) => void;
  gps: ReturnType<typeof useBrowserGps>;
}

/**
 * "Time since last visit: 1 day 3 h (last visit 17 Nov, 15:26)" and where the last visit was. The last
 * visit is the latest reading on any of the machine's reports (rejected ones too).
 */
function LastVisit({
  context,
  capturedAt,
  timeZone,
}: {
  context: MachineReportContextDto;
  capturedAt: string;
  timeZone: string;
}) {
  const at = context.last_visit_at ?? null;
  const gap = formatVisitGap(secondsBetween(at, capturedAt));
  return (
    <Stack spacing={0.5} role="status">
      <Typography variant="body1">
        Time since last visit: {gap}
        {at === null ? '' : ` (last visit ${formatVisitAt(at, timeZone)})`}
      </Typography>
      <VisitWhere
        place={{
          place: context.last_visit_place,
          site: context.last_visit_site_name,
          lat: context.last_visit_lat,
          lng: context.last_visit_lng,
          accuracy: context.last_visit_accuracy_m,
        }}
      />
    </Stack>
  );
}

function ReadingStep({ context, rules, capturedAt, photo, onPhotoChange, gps }: ReadingStepProps) {
  const timeZone = useDisplayTimeZone();
  const { values } = useFormikContext<ReportValues>();
  const difference = meterDifference(rules, values.reading);
  return (
    <>
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Machine', value: context.machine_name ?? context.machine_code ?? '—' },
          {
            label: 'Last reading',
            value:
              context.previous_reading === null
                ? 'None yet'
                : [
                    hoursLabel(context.previous_reading),
                    context.previous_at === null
                      ? null
                      : formatInstantIn(context.previous_at, timeZone),
                    context.previous_source === null
                      ? null
                      : START_SOURCE_LABELS[context.previous_source],
                  ]
                    .filter((x) => x !== null)
                    .join(' · '),
          },
        ]}
      />
      <Typography variant="body2">
        Reading looks wrong or the meter was replaced?{' '}
        <Link component={RouterLink} to={ROUTES.fieldReadings}>
          Readings and meter resets
        </Link>
      </Typography>
      {rules.opening && (
        <Alert severity="info">
          This machine has no starting reading yet. Record its reading now: once approved it is the
          starting point of the next report. There are no hours to split this time.
        </Alert>
      )}
      <CaptureEvidenceFields
        machineId={context.machine_id}
        kind="DAILY"
        captureMode={values.capture_mode}
        photo={photo}
        onPhotoChange={onPhotoChange}
        gps={gps.gps}
        onRetryGps={gps.retry}
      />
      {values.reading.trim() !== '' && (
        <LastVisit context={context} capturedAt={capturedAt} timeZone={timeZone} />
      )}
      {difference !== null && isDecimalString(difference) && (
        <Typography variant="h6" component="p" role="status">
          {compareDecimal(difference, '0') > 0
            ? `Hours to account for: ${hoursLabel(difference)}`
            : compareDecimal(difference, '0') === 0
              ? 'No difference since the last reading? Nothing to report.'
              : 'The new reading is lower than the last one. Check the number on the meter.'}
        </Typography>
      )}
    </>
  );
}

interface FormProps {
  context: MachineReportContextDto;
  onClose: () => void;
  onSubmitted: (report: MachineReportDto) => void;
}

function ReportForm({ context, onClose, onSubmitted }: FormProps) {
  const keyFor = useIdempotencyKey();
  const gps = useBrowserGps();
  const [reportId] = useState(newUuid);
  const [captureId] = useState(newUuid);
  const [capturedAt] = useState(() => new Date().toISOString());
  const [photo, setPhoto] = useState<AttachmentDto | null>(null);
  const [initial] = useState(emptyReportValues);
  const customers: readonly AvailableHoursDto[] = context.customers;
  // The server says whether this is an opening report (the machine's first reading).
  const opening = context.opening_required;
  const rules = useMemo<ReportRules>(
    () => ({
      previous: opening ? null : context.previous_reading,
      opening,
      available: Object.fromEntries(customers.map((c) => [c.customer_id, c.available])),
    }),
    [context, customers, opening],
  );
  const schema = useMemo(() => reportSchema(rules), [rules]);
  const label = context.machine_code ?? context.machine_name ?? 'machine';
  return (
    <StepperFormDialog<ReportValues>
      open
      title={`Machine report · ${label}`}
      initialValues={initial}
      validationSchema={schema}
      submitLabel="Submit for approval"
      onClose={onClose}
      steps={[
        {
          label: 'Reading',
          fields: READING_FIELDS,
          render: () => (
            <ReadingStep
              context={context}
              rules={rules}
              capturedAt={capturedAt}
              photo={photo}
              onPhotoChange={setPhoto}
              gps={gps}
            />
          ),
        },
        ...(opening
          ? []
          : [
              {
                label: 'Account for hours',
                fields: ['lines', 'note'],
                fieldsFor: lineFieldsFor,
                render: () => (
                  <ReportLinesStep
                    machineId={context.machine_id}
                    rules={rules}
                    customers={customers}
                    reasons={context.reasons}
                    hoursOn
                  />
                ),
              },
            ]),
      ]}
      renderReview={(v) => (
        <ReportReview
          values={v}
          rules={rules}
          machineLabel={label}
          customers={customers}
          reasons={context.reasons}
          photoAttached={photo !== null}
        />
      )}
      onSubmit={async (v) => {
        if (gps.gps === null) throw gpsPendingError();
        const body = toReportPayload(v, {
          reportId,
          machineId: context.machine_id,
          opening,
          evidence: {
            captureId,
            capturedAt,
            gps: gps.gps,
            photoId: photo?.id ?? null,
          },
        });
        try {
          onSubmitted(await machineReportService.submit(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, REPORT_ERROR_HINTS);
        }
      }}
    />
  );
}

export interface MachineReportDialogProps {
  machineId: string;
  onClose: () => void;
  onSubmitted: (report: MachineReportDto) => void;
}

/**
 * Reading → Account for hours → Review. Loads the machine's report context first: the previous
 * reading, usable customer hours and the reason list. A machine with a report waiting for a decision
 * cannot take another one; a machine with no starting reading takes an opening report (reading only).
 */
export function MachineReportDialog({ machineId, onClose, onSubmitted }: MachineReportDialogProps) {
  const load = useCallback(
    (signal: AbortSignal) => machineReportService.context(machineId, signal),
    [machineId],
  );
  const res = useAsyncResource(load);
  const context = res.data;
  if (context !== null && context.pending_report_id === null) {
    return <ReportForm context={context} onClose={onClose} onSubmitted={onSubmitted} />;
  }
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Machine report</DialogTitle>
      <DialogContent>
        <AsyncContent resource={res} errorTitle="Could not load the machine">
          {() => (
            <Alert severity="info">
              A report on this machine is waiting for a decision. The next report can be sent once
              it is approved or rejected.
            </Alert>
          )}
        </AsyncContent>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
