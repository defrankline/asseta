import { array, mixed, object, string, type ObjectSchema } from 'yup';
import type {
  MachineReportIn,
  MachineReportLineIn,
  ReportLineKind,
} from '../../../api/machineReportTypes';
import type { CaptureMode, GpsIn } from '../../../api/types';
import { compareDecimal, isDecimalString, signOfDecimal, sumDecimals } from '../../../utils/money';
import { optionalText, orNull } from '../shared/formRules';
import { CONSOLE_DEVICE_ID } from '../readings/capturePolicy';
import { captureModeField } from '../readings/readingEvidenceKit';
import { hoursLabel, inMeterSteps, minus, plainHours } from './machineReportDisplay';

/** One line of the split: a customer's hours or non-productive hours with a reason and a note. */
export interface LineValues {
  /** Stable React key only; never sent. */
  key: string;
  kind: ReportLineKind;
  customer_id: string;
  reason_id: string;
  hours: string;
  note: string;
  /** Hours the form filled in itself (never sent); while `hours` still equals it, picking a customer may replace it. */
  autoHours?: string;
}

export interface ReportValues {
  capture_mode: CaptureMode | '';
  reading: string;
  lines: LineValues[];
  note: string;
}

/** What the form checks against: from the machine's report context (the server decides). */
export interface ReportRules {
  /** Where the report starts; null = no starting reading yet. */
  previous: string | null;
  /** An opening report (`opening_required` in the context): the machine's first reading only, no lines. */
  opening: boolean;
  /** Usable hours per customer for this report. */
  available: Readonly<Record<string, string>>;
}

export const READING_FIELDS = ['capture_mode', 'reading'] as const;

export function lineFieldsFor(v: ReportValues): string[] {
  return [
    'lines',
    'note',
    ...v.lines.flatMap((_, i) => [
      `lines[${i}].customer_id`,
      `lines[${i}].reason_id`,
      `lines[${i}].hours`,
      `lines[${i}].note`,
    ]),
  ];
}

export function emptyLine(kind: ReportLineKind, hours = ''): LineValues {
  return {
    key: Math.random().toString(36).slice(2),
    kind,
    customer_id: '',
    reason_id: '',
    hours,
    note: '',
    autoHours: hours,
  };
}

export function emptyReportValues(): ReportValues {
  return { capture_mode: '', reading: '', lines: [], note: '' };
}

/** Line hours have at most 2 decimals (steps of 0.01), whatever the meter's precision. */
export const LINE_DECIMALS = 2;

const positiveHours = (v: string) => isDecimalString(v) && signOfDecimal(v) > 0;

/** Valid line hours: a number above 0 with at most 2 decimals. */
export function lineHoursValid(hours: string): boolean {
  const v = hours.trim();
  return positiveHours(v) && inMeterSteps(v, LINE_DECIMALS);
}

const text = (v: unknown): string => (typeof v === 'string' ? v : '');

/** Lines as Formik validates them (it turns empty strings into undefined). */
function normalized(lines: readonly LineValues[]): LineValues[] {
  return lines.map((l) => ({
    ...l,
    customer_id: text(l.customer_id),
    reason_id: text(l.reason_id),
    hours: text(l.hours),
    note: text(l.note),
  }));
}

/** Sum of the lines with valid hours (a line with invalid hours counts for nothing). */
export function accountedFor(lines: readonly LineValues[]): string {
  return sumDecimals(['0', ...lines.map((l) => l.hours.trim()).filter(lineHoursValid)]);
}

/** Every line has valid hours. */
export function allLinesValid(lines: readonly LineValues[]): boolean {
  return lines.every((l) => lineHoursValid(l.hours));
}

/** "All hours accounted for": every line valid and the lines add up exactly to the difference. */
export function allAccountedFor(lines: readonly LineValues[], difference: string | null): boolean {
  return (
    difference !== null &&
    allLinesValid(lines) &&
    balanceText(difference, accountedFor(lines)) === null
  );
}

/** Hours the meter moved since the previous reading; null while unknown or not a number. */
export function meterDifference(rules: ReportRules, reading: string): string | null {
  const end = reading.trim();
  if (rules.previous === null || !isDecimalString(end)) return null;
  return minus(end, rules.previous);
}

/** A customer's hours on this report (all their lines). */
export function customerTotal(lines: readonly LineValues[], customerId: string): string {
  return accountedFor(lines.filter((l) => l.kind === 'CUSTOMER' && l.customer_id === customerId));
}

/** A positive decimal, or null for 0 and below. */
const positiveOrNull = (v: string): string | null => (signOfDecimal(v) > 0 ? v : null);

/**
 * Hours a customer still has for this report once the other lines are counted (line `index`
 * left out); null when none are left.
 */
export function customerHoursLeft(
  lines: readonly LineValues[],
  index: number,
  customerId: string,
  available: string,
): string | null {
  const others = lines.filter((_, j) => j !== index);
  return positiveOrNull(minus(available, customerTotal(others, customerId)));
}

/**
 * Hours to fill in when a customer is picked on line `index`: the smaller of the hours the customer
 * still has and the hours still to account for (other lines counted). Null = leave the line as is
 * (nothing left on one side, or the meter difference unknown).
 */
export function suggestedCustomerHours(
  lines: readonly LineValues[],
  index: number,
  customerId: string,
  available: string,
  difference: string | null,
): string | null {
  if (difference === null) return null;
  const customerLeft = customerHoursLeft(lines, index, customerId, available);
  const machineLeft = positiveOrNull(
    minus(difference, accountedFor(lines.filter((_, j) => j !== index))),
  );
  if (customerLeft === null || machineLeft === null) return null;
  return plainHours(compareDecimal(customerLeft, machineLeft) <= 0 ? customerLeft : machineLeft);
}

/** Whether picking a customer may replace the line's hours: empty, or still what the form filled in. */
export function hoursAreAuto(line: LineValues): boolean {
  const hours = line.hours.trim();
  return hours === '' || (line.autoHours !== undefined && hours === line.autoHours.trim());
}

/** "15 h still to account for" / "10 h more than the meter" / null when it matches. */
export function balanceText(difference: string, accounted: string): string | null {
  const left = minus(difference, accounted);
  const sign = signOfDecimal(left);
  if (sign === 0) return null;
  return sign > 0
    ? `${hoursLabel(left)} still to account for`
    : `${hoursLabel(minus('0', left))} more than the meter shows`;
}

export function reportSchema(rules: ReportRules): ObjectSchema<ReportValues> {
  const lineSchema = object({
    key: string().required(),
    kind: mixed<ReportLineKind>().oneOf(['CUSTOMER', 'NON_PRODUCTIVE']).required(),
    customer_id: string()
      .ensure()
      .test('customer', 'Choose the customer', function (v) {
        return (this.parent as LineValues).kind !== 'CUSTOMER' || v !== '';
      }),
    reason_id: string()
      .ensure()
      .test('reason', 'Choose the reason', function (v) {
        return (this.parent as LineValues).kind !== 'NON_PRODUCTIVE' || v !== '';
      }),
    hours: string()
      .trim()
      .required('Enter the hours')
      .test('positive', 'Enter hours above 0', positiveHours)
      .test(
        'steps',
        'Hours have at most 2 decimals',
        (v) => !positiveHours(v) || inMeterSteps(v, LINE_DECIMALS),
      ),
    note: optionalText('Note', 1000).test(
      'note',
      'Say what happened (a note is required for non-productive hours)',
      function (v) {
        return (this.parent as LineValues).kind !== 'NON_PRODUCTIVE' || v.trim() !== '';
      },
    ),
  });
  return object({
    capture_mode: captureModeField(),
    reading: string()
      .ensure()
      .test('reading', 'Reading is required', (v) => v.trim() !== '')
      .test('format', 'Enter the meter reading as shown (up to 4 decimals)', (v) =>
        /^\d+(\.\d{1,4})?$/.test(v.trim()),
      )
      .test('higher', 'The new reading must be higher than the last one', (v) => {
        if (rules.previous === null || !isDecimalString(v)) {
          return true;
        }
        return compareDecimal(v.trim(), rules.previous) > 0;
      }),
    lines: array(lineSchema)
      .required()
      .test('one-per-customer', 'Put each customer on one line only', (raw) => {
        const ids = normalized(raw).filter((l) => l.kind === 'CUSTOMER' && l.customer_id !== '');
        return new Set(ids.map((l) => l.customer_id)).size === ids.length;
      })
      .test('available', 'A customer gets more hours than they have usable', (raw) =>
        normalized(raw).every(
          (l) =>
            l.kind !== 'CUSTOMER' ||
            l.customer_id === '' ||
            compareDecimal(
              customerTotal(normalized(raw), l.customer_id),
              rules.available[l.customer_id] ?? '0',
            ) <= 0,
        ),
      )
      .test('sum', 'The lines must add up to the meter hours', function (raw) {
        if (rules.opening || rules.previous === null) return true;
        const difference = meterDifference(rules, text((this.parent as ReportValues).reading));
        if (difference === null) return true;
        const left = balanceText(difference, accountedFor(normalized(raw)));
        return left === null ? true : this.createError({ message: left });
      }),
    note: optionalText('Note', 1000),
  });
}

interface CaptureEvidence {
  captureId: string;
  capturedAt: string;
  /** The browser's real GPS outcome. */
  gps: GpsIn | null;
  photoId: string | null;
}

/**
 * submitMachineReport body: always a new DAILY reading and the split (a rejected report is final: never
 * `corrects_report_id`); an
 * opening report sends `opening: true` with no lines. The new reading goes inline as `capture`:
 * REST takes it in the same request as the report (the phones send it as a METER_CAPTURE operation
 * first and then `capture_id`), so a supervisor holding only the machine-report permission can send it.
 */
export function toReportPayload(
  v: ReportValues,
  options: {
    reportId: string;
    machineId: string;
    evidence: CaptureEvidence;
    /** An opening report: the reading only. */
    opening: boolean;
  },
): MachineReportIn {
  const lines: MachineReportLineIn[] = options.opening
    ? []
    : v.lines.map((l) =>
        l.kind === 'CUSTOMER'
          ? { kind: 'CUSTOMER', customer_id: l.customer_id, hours: l.hours.trim() }
          : {
              kind: 'NON_PRODUCTIVE',
              reason_id: l.reason_id,
              hours: l.hours.trim(),
              note: l.note.trim(),
            },
      );
  const base = {
    id: options.reportId,
    machine_id: options.machineId,
    opening: options.opening,
    lines,
    note: orNull(v.note),
    client_created_at: options.evidence.capturedAt,
  };
  const { evidence } = options;
  if (evidence.gps === null) throw new Error('A new reading needs the GPS outcome');
  return {
    ...base,
    capture: {
      id: evidence.captureId,
      kind: 'DAILY',
      machine_id: options.machineId,
      capture_mode: v.capture_mode === '' ? 'MANUAL' : v.capture_mode,
      reading: v.reading.trim(),
      gps: evidence.gps,
      device_id: CONSOLE_DEVICE_ID,
      captured_at: evidence.capturedAt,
      photo_attachment_id: evidence.photoId,
      ocr_value: null,
      ocr_confidence: null,
    },
  };
}
