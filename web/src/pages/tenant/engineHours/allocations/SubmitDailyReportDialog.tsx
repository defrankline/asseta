import Add from '@mui/icons-material/Add';
import DeleteOutlined from '@mui/icons-material/DeleteOutlined';
import { Alert, Box, Button, IconButton, Typography } from '@mui/material';
import { FieldArray, type FormikProps } from 'formik';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { array, object, string, type ObjectSchema } from 'yup';
import { ApiError } from '../../../../api/ApiError';
import type {
  DailyReportDto,
  DailyReportIn,
  DailyReportPrefillDto,
} from '../../../../api/allocationTypes';
import { newUuid } from '../../../../api/ids';
import { allocationService } from '../../../../api/services/allocationService';
import type { AttachmentDto, EngineHourReasonDto } from '../../../../api/types';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { AsyncContent } from '../../../../components/feedback/AsyncContent';
import { FormDialog } from '../../../../components/forms/FormDialog';
import { FormikAsyncIdAutocomplete } from '../../../../components/forms/FormikAsyncIdAutocomplete';
import { FormikDateField } from '../../../../components/forms/FormikDateField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { todayIsoDate } from '../../../../utils/dates';
import { FormikFieldMachineIdPicker } from '../../field/fieldPickers';
import { withErrorCode } from '../../shared/errorHints';
import { optionId } from '../../shared/lookups';
import { machineText } from '../../shared/names';
import { ENGINE_HOURS_ERROR_HINTS, hoursText } from '../engineHoursDisplay';
import { reasonLabel, resolveReason, searchReasons } from '../engineHoursLookups';
import {
  allocationTarget,
  fromHundredths,
  HOURS_PATTERN,
  KIND_LABELS,
  toHundredths,
} from './allocationDisplay';
import { EvidenceUpload } from './EvidenceUpload';
import { useEngineHoursRules } from './useEngineHoursPolicy';

/** The server takes at most this many unbillable lines on one report. */
const MAX_LINES = 20;

interface LineValues {
  reason_id: string;
  hours: string;
}

interface ReportValues {
  machine_id: string;
  report_date: string;
  billable_hours: string;
  unbillable: LineValues[];
  note: string;
}

const lineSchema: ObjectSchema<LineValues> = object({
  reason_id: string().required('Choose the reason'),
  hours: string()
    .trim()
    .required('Hours are required')
    .matches(HOURS_PATTERN, 'Up to 2 decimals')
    .test('positive', 'More than 0', (v) => Number(v) > 0),
});

const schema: ObjectSchema<ReportValues> = object({
  machine_id: string().required('Choose the machine'),
  report_date: string().required('Choose the day'),
  billable_hours: string()
    .trim()
    .ensure()
    .test('hours', 'Up to 2 decimals', (v) => v === '' || HOURS_PATTERN.test(v)),
  unbillable: array(lineSchema).max(MAX_LINES).required(),
  note: string().trim().ensure().max(2000, 'At most 2000 characters'),
});

const searchUnbillable = searchReasons('UNBILLABLE_REASON');

const refusal = (message: string) =>
  new ApiError({ status: null, code: 'report_incomplete', message, correlationId: null });

function DayPrefill({
  machineId,
  reportDate,
  replacing,
  onLoaded,
}: {
  machineId: string;
  reportDate: string;
  replacing: boolean;
  onLoaded: (p: DailyReportPrefillDto | null) => void;
}) {
  const load = useCallback(
    (signal: AbortSignal) => allocationService.prefillReport(machineId, reportDate, signal),
    [machineId, reportDate],
  );
  const res = useAsyncResource(load, [machineId, reportDate]);
  useEffect(() => {
    onLoaded(res.data);
  }, [res.data, onLoaded]);
  return (
    <AsyncContent resource={res} errorTitle="Could not load the day's readings">
      {(p) => (
        <>
          {(p.opening_ref === null || p.closing_ref === null) && (
            <Alert severity="warning">
              This day needs an opening and a closing reading before it can be reported.
            </Alert>
          )}
          {!replacing && p.existing_report_ids.length > 0 && (
            <Alert severity="warning">
              A report for this machine and day already exists. Submitting another keeps both and
              flags this one as a duplicate.
            </Alert>
          )}
          <KeyValueGrid
            columns={3}
            items={[
              { label: 'Opening reading', value: p.opening_reading ?? '—' },
              { label: 'Closing reading', value: p.closing_reading ?? '—' },
              { label: 'Total hours', value: hoursText(p.total_hours) },
              { label: 'Customer work', value: hoursText(p.customer_hours) },
              { label: 'Authorized activity', value: hoursText(p.authorized_hours) },
              { label: 'Unexplained', value: hoursText(p.unexplained_hours) },
            ]}
          />
          {p.allocations.length > 0 && (
            <Box component="ul" className="m-0 pl-4" aria-label="The day's allocations">
              {p.allocations.map((a) => (
                <Typography key={a.allocation_id} component="li" variant="body2">
                  {a.hours} h · {KIND_LABELS[a.kind]} · {allocationTarget(a)}
                </Typography>
              ))}
            </Box>
          )}
        </>
      )}
    </AsyncContent>
  );
}

function UnbillableLines({ formik }: { formik: FormikProps<ReportValues> }) {
  const lines = formik.values.unbillable;
  return (
    <FieldArray name="unbillable">
      {(helpers) => (
        <Box className="flex flex-col gap-2">
          <Typography variant="subtitle2" component="h3">
            Unbillable hours by reason
          </Typography>
          {lines.map((_l, i) => (
            <Box key={i} className="grid grid-cols-[1fr_8rem_auto] items-start gap-2">
              <FormikAsyncIdAutocomplete<EngineHourReasonDto>
                name={`unbillable.${String(i)}.reason_id`}
                label="Reason"
                required
                fetchOptions={searchUnbillable}
                resolveOption={resolveReason}
                getOptionId={optionId}
                getOptionLabel={reasonLabel}
                noOptionsText="No unbillable reasons yet (Engine hours lists)"
              />
              <FormikTextField name={`unbillable.${String(i)}.hours`} label="Hours" required />
              <IconButton
                size="small"
                aria-label={`Remove line ${String(i + 1)}`}
                onClick={() => {
                  helpers.remove(i);
                }}
              >
                <DeleteOutlined fontSize="small" />
              </IconButton>
            </Box>
          ))}
          <Box>
            <Button
              size="small"
              startIcon={<Add />}
              disabled={lines.length >= MAX_LINES}
              onClick={() => {
                helpers.push({ reason_id: '', hours: '' });
              }}
            >
              Add unbillable hours
            </Button>
          </Box>
        </Box>
      )}
    </FieldArray>
  );
}

const unbillableTotal = (lines: readonly LineValues[]): number =>
  lines.reduce((n, l) => n + (HOURS_PATTERN.test(l.hours) ? toHundredths(l.hours) : 0), 0);

interface SubmitDailyReportDialogProps {
  /** Replaces this report (same machine and day), e.g. one that was returned. */
  replaces?: DailyReportDto;
  onClose: () => void;
  onSubmitted: (report: DailyReportDto) => void;
}

/**
 * A machine's report for one day, pre-filled from its readings and allocations. The two readings
 * come from the day itself; a wrong reading is fixed through a reading correction, not here.
 */
export function SubmitDailyReportDialog({
  replaces,
  onClose,
  onSubmitted,
}: SubmitDailyReportDialogProps) {
  const [reportId] = useState(newUuid);
  const [createdAt] = useState(() => new Date().toISOString());
  const keyFor = useIdempotencyKey();
  const [prefill, setPrefill] = useState<DailyReportPrefillDto | null>(null);
  const [evidence, setEvidence] = useState<AttachmentDto[]>([]);
  const [machineId, setMachineId] = useState<string | null>(replaces?.machine_id ?? null);
  const { reportEvidenceRequired } = useEngineHoursRules(machineId);
  const initial = useMemo<ReportValues>(
    () => ({
      machine_id: replaces?.machine_id ?? '',
      report_date: replaces?.report_date ?? todayIsoDate(),
      billable_hours: '',
      unbillable:
        replaces?.unbillable.map((u) => ({ reason_id: u.reason_id, hours: u.hours })) ?? [],
      note: '',
    }),
    [replaces],
  );
  const title =
    replaces === undefined
      ? 'New daily report'
      : `Replace report · ${machineText(replaces.machine_code, replaces.machine_name, replaces.machine_id)}`;
  return (
    <FormDialog<ReportValues>
      open
      title={title}
      initialValues={initial}
      validationSchema={schema}
      submitLabel="Submit report"
      maxWidth="md"
      onClose={onClose}
      onSubmit={async (v) => {
        const matches =
          prefill !== null &&
          prefill.machine_id === v.machine_id &&
          prefill.report_date === v.report_date;
        if (!matches || prefill.opening_ref === null || prefill.closing_ref === null) {
          throw refusal('This day needs an opening and a closing reading first.');
        }
        const billable = v.billable_hours.trim();
        const declared =
          unbillableTotal(v.unbillable) + (billable === '' ? 0 : toHundredths(billable));
        if (prefill.total_hours !== null && declared > toHundredths(prefill.total_hours)) {
          throw refusal(
            `Billable and unbillable hours (${fromHundredths(declared)}) are more than the day's ${prefill.total_hours} h.`,
          );
        }
        if (reportEvidenceRequired && evidence.length === 0) {
          throw refusal('Your company requires a photo with daily reports; attach one.');
        }
        const note = v.note.trim();
        const body: DailyReportIn = {
          id: reportId,
          machine_id: v.machine_id,
          report_date: v.report_date,
          opening_ref: prefill.opening_ref,
          closing_ref: prefill.closing_ref,
          billable_hours: billable === '' ? null : billable,
          unbillable: v.unbillable.map((l) => ({ reason_id: l.reason_id, hours: l.hours.trim() })),
          note: note === '' ? null : note,
          evidence_attachment_ids: evidence.map((a) => a.id),
          supersedes_id: replaces?.id ?? null,
          client_created_at: createdAt,
        };
        try {
          onSubmitted(await allocationService.submitReport(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, ENGINE_HOURS_ERROR_HINTS);
        }
      }}
    >
      {(formik) => {
        const { machine_id: chosenMachine, report_date: reportDate } = formik.values;
        return (
          <>
            <Box className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <FormikFieldMachineIdPicker
                name="machine_id"
                label="Machine"
                required
                disabled={replaces !== undefined}
                onOptionChange={(m) => {
                  setMachineId(m?.id ?? null);
                }}
              />
              <FormikDateField
                name="report_date"
                label="Report date"
                required
                disabled={replaces !== undefined}
                maxDate={todayIsoDate()}
              />
            </Box>
            {chosenMachine !== '' && reportDate !== '' && (
              <DayPrefill
                machineId={chosenMachine}
                reportDate={reportDate}
                replacing={replaces !== undefined}
                onLoaded={setPrefill}
              />
            )}
            <FormikTextField
              name="billable_hours"
              label="Billable hours"
              helperText="Leave empty to use the total minus the unbillable hours."
            />
            <UnbillableLines formik={formik} />
            <FormikTextField name="note" label="Note" multiline minRows={2} />
            <EvidenceUpload
              value={evidence}
              onChange={setEvidence}
              purpose="DAILY_REPORT_EVIDENCE"
              required={reportEvidenceRequired}
            />
          </>
        );
      }}
    </FormDialog>
  );
}
