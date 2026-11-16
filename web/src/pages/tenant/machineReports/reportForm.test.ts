import { describe, expect, it } from 'vitest';
import { REPORT } from './machineReportFixtures';
import {
  emptyLine,
  reportSchema,
  toReportPayload,
  type ReportRules,
  type ReportValues,
} from './reportForm';

const RULES: ReportRules = {
  previous: '1210.0',
  decimals: 1,
  fixedReading: null,
  available: { c1: '140' },
};
const values = (over: Partial<ReportValues>): ReportValues => ({
  capture_mode: 'MANUAL',
  reading: '1510.0',
  note: '',
  lines: [],
  ...over,
});
const line = (kind: 'CUSTOMER' | 'NON_PRODUCTIVE', hours: string, id: string, note = '') => ({
  ...emptyLine(kind, hours),
  customer_id: kind === 'CUSTOMER' ? id : '',
  reason_id: kind === 'NON_PRODUCTIVE' ? id : '',
  note,
});
const errorsOf = (v: ReportValues, rules = RULES) => {
  try {
    reportSchema(rules).validateSync(v, { abortEarly: false });
    return [];
  } catch (e) {
    return (e as { errors: string[] }).errors;
  }
};

describe('machine report rules', () => {
  it('needs the lines to add up exactly to the meter difference', () => {
    const short = values({ lines: [line('CUSTOMER', '120', 'c1')] });
    expect(errorsOf(short)).toContain('180 h still to account for');
    const over = values({
      lines: [line('CUSTOMER', '120', 'c1'), line('NON_PRODUCTIVE', '200', 'r1', 'Hose')],
    });
    expect(errorsOf(over)).toContain('20 h more than the meter shows');
    const exact = values({
      lines: [line('CUSTOMER', '120', 'c1'), line('NON_PRODUCTIVE', '180', 'r1', 'Hose')],
    });
    expect(errorsOf(exact)).toEqual([]);
  });

  it('keeps customers within their usable hours, one line each, in the meter steps', () => {
    expect(
      errorsOf(values({ reading: '1360.0', lines: [line('CUSTOMER', '150', 'c1')] })),
    ).toContain('A customer gets more hours than they have usable');
    expect(
      errorsOf(
        values({
          reading: '1230.0',
          lines: [line('CUSTOMER', '10', 'c1'), line('CUSTOMER', '10', 'c1')],
        }),
      ),
    ).toContain('Put each customer on one line only');
    expect(
      errorsOf(values({ reading: '1210.25', lines: [line('CUSTOMER', '0.25', 'c1')] })),
    ).toContain('Use at most 1 decimal(s), as the meter shows');
  });

  it('needs a reason and a note for non-productive hours, and a higher reading', () => {
    const errors = errorsOf(
      values({ reading: '1200', lines: [line('NON_PRODUCTIVE', '10', '', '')] }),
    );
    expect(errors).toContain('Choose the reason');
    expect(errors).toContain('Say what happened (a note is required for non-productive hours)');
    expect(errors).toContain('The new reading must be higher than the last one');
  });

  it('sends a new reading, or the rejected report’s reading when correcting', () => {
    const v = values({
      lines: [line('CUSTOMER', '120', 'c1'), line('NON_PRODUCTIVE', '180', 'r1', ' Hose ')],
    });
    const evidence = {
      captureId: 'cap9',
      capturedAt: '2026-11-16T05:00:00Z',
      gps: { status: 'FIX' as const },
      photoId: 'ph1',
    };
    const fresh = toReportPayload(v, {
      reportId: 'id1',
      machineId: 'm1',
      evidence,
      corrects: null,
    });
    expect(fresh.capture).toMatchObject({ id: 'cap9', kind: 'DAILY', reading: '1510.0' });
    expect(fresh.lines[1]).toEqual({
      kind: 'NON_PRODUCTIVE',
      reason_id: 'r1',
      hours: '180',
      note: 'Hose',
    });
    expect(fresh).not.toHaveProperty('opening');
    const fixed = toReportPayload(v, {
      reportId: 'id2',
      machineId: 'm1',
      evidence: { ...evidence, gps: null },
      corrects: { ...REPORT, status: 'REJECTED' },
    });
    expect(fixed).toMatchObject({ capture_id: 'cap1', corrects_report_id: 'mr1' });
    expect(fixed).not.toHaveProperty('capture');
    const opening = toReportPayload(values({ lines: [] }), {
      reportId: 'id3',
      machineId: 'm1',
      evidence,
      corrects: null,
    });
    expect(opening).toMatchObject({ opening: true, lines: [] });
  });
});
