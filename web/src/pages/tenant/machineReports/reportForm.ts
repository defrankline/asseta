import { array, mixed, object, string, type ObjectSchema } from 'yup';
import type {
  MachineReportDto,
  MachineReportIn,
  MachineReportLineIn,
  ReportLineKind,
} from '../../../api/machineReportTypes';
import type { CaptureMode, GpsIn } from '../../../api/types';
import { compareDecimal, isDecimalString, signOfDecimal, sumDecimals } from '../../../utils/money';
import { optionalText, orNull } from '../shared/formRules';
import { CONSOLE_DEVICE_ID } from '../readings/capturePolicy';
import { captureModeField } from '../readings/readingEvidenceKit';
import { hoursLabel, inMeterSteps, minus } from './machineReportDisplay';

/** One line of the split: a customer's hours or non-productive hours with a reason and a note. */
export interface LineValues {
  /** Stable React key only; never sent. */
  key: string;
  kind: ReportLineKind;
  customer_id: string;
  reason_id: string;
  hours: string;
  note: string;
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
  /**
   * An opening report (`opening_required` in the context, or correcting a rejected opening report):
   * the machine's first reading only, no lines.
   */
  opening: boolean;
  decimals: number;
  /** A correction keeps the rejected report's reading. */
  fixedReading: string | null;
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
  };
}

export function emptyReportValues(): ReportValues {
  return { capture_mode: '', reading: '', lines: [], note: '' };
}

/** The rejected report's lines, to correct them on the same reading. */
export function correctionValues(rejected: MachineReportDto): ReportValues {
  return {
    capture_mode: 'MANUAL',
    reading: rejected.end_reading,
    note: '',
    lines: rejected.lines.map((l) => ({
      ...emptyLine(l.kind, l.hours),
      customer_id: l.customer_id ?? '',
      reason_id: l.reason_id ?? '',
      note: l.note ?? '',
    })),
  };
}

const validHours = (v: string) => isDecimalString(v) && signOfDecimal(v) > 0;

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

/** Sum of the lines with valid hours. */
export function accountedFor(lines: readonly LineValues[]): string {
  return sumDecimals(['0', ...lines.map((l) => l.hours.trim()).filter(validHours)]);
}

/** Hours the meter moved since the previous reading; null while unknown or not a number. */
export function meterDifference(rules: ReportRules, reading: string): string | null {
  const end = rules.fixedReading ?? reading.trim();
  if (rules.previous === null || !isDecimalString(end)) return null;
  return minus(end, rules.previous);
}

/** A customer's hours on this report (all their lines). */
export function customerTotal(lines: readonly LineValues[], customerId: string): string {
  return accountedFor(lines.filter((l) => l.kind === 'CUSTOMER' && l.customer_id === customerId));
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
      .test('positive', 'Enter hours above 0', validHours)
      .test(
        'steps',
        rules.decimals === 0
          ? 'Use whole hours (the meter shows whole hours)'
          : `Use at most ${String(rules.decimals)} decimal(s), as the meter shows`,
        (v) => !validHours(v) || inMeterSteps(v, rules.decimals),
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
    capture_mode:
      rules.fixedReading === null ? captureModeField() : mixed<CaptureMode | ''>().defined(),
    reading: string()
      .ensure()
      .test('reading', 'Reading is required', (v) => rules.fixedReading !== null || v.trim() !== '')
      .test(
        'format',
        'Enter the meter reading as shown (up to 4 decimals)',
        (v) => rules.fixedReading !== null || /^\d+(\.\d{1,4})?$/.test(v.trim()),
      )
      .test('higher', 'The new reading must be higher than the last one', (v) => {
        if (rules.fixedReading !== null || rules.previous === null || !isDecimalString(v)) {
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
  /** The browser's real GPS outcome (null only for a correction: no new reading). */
  gps: GpsIn | null;
  photoId: string | null;
}

/**
 * submitMachineReport body: a new DAILY reading (or the rejected report's reading) and the split; an
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
    /** Correcting this rejected report on its reading. */
    corrects: MachineReportDto | null;
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
  if (options.corrects !== null) {
    return {
      ...base,
      capture_id: options.corrects.capture_id,
      corrects_report_id: options.corrects.id,
    };
  }
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
