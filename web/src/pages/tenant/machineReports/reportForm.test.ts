import { describe, expect, it } from 'vitest';
import { machineReportState } from './machineReportDisplay';
import { STATUS } from './machineReportFixtures';
import {
  accountedFor,
  allAccountedFor,
  allLinesValid,
  customerHoursLeft,
  customerTotal,
  emptyLine,
  hoursAreAuto,
  lineHoursValid,
  reportSchema,
  suggestedCustomerHours,
  toReportPayload,
  type ReportRules,
  type ReportValues,
} from './reportForm';

const RULES: ReportRules = {
  previous: '1210.0',
  opening: false,
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
    // Line hours take 2 decimals whatever the meter's precision; the sum must still be exact.
    expect(
      errorsOf(
        values({
          reading: '1219.0',
          lines: [line('CUSTOMER', '8.85', 'c1'), line('NON_PRODUCTIVE', '0.15', 'r1', 'Wait')],
        }),
      ),
    ).toEqual([]);
    expect(
      errorsOf(values({ reading: '1210.3', lines: [line('CUSTOMER', '0.255', 'c1')] })),
    ).toContain('Hours have at most 2 decimals');
  });

  it('does not count a line with invalid hours as accounted for', () => {
    expect(lineHoursValid('1.15')).toBe(true);
    expect(lineHoursValid(' 7.85 ')).toBe(true);
    for (const bad of ['', '0', '-1', 'abc', '1.155', '1.2.3']) {
      expect(lineHoursValid(bad)).toBe(false);
    }
    // The meter moved 9 h; a customer line of 9 h and a second line with invalid hours.
    const lines = [line('CUSTOMER', '9', 'c1'), line('CUSTOMER', '1.155', 'c2')];
    expect(accountedFor(lines)).toBe('9');
    expect(allLinesValid(lines)).toBe(false);
    // The sum matches, but not every line is valid: not "all hours accounted for".
    expect(allAccountedFor(lines, '9')).toBe(false);
    // The customer's "after this" ignores the invalid line.
    expect(customerTotal(lines, 'c2')).toBe('0');
    expect(
      errorsOf(values({ reading: '1219.0', lines }), {
        ...RULES,
        available: { c1: '140', c2: '140' },
      }),
    ).toEqual(['Hours have at most 2 decimals']);
    const ok = [line('CUSTOMER', '7.85', 'c1'), line('CUSTOMER', '1.15', 'c2')];
    expect(allAccountedFor(ok, '9.0')).toBe(true);
    expect(allAccountedFor(ok, '9.1')).toBe(false);
    expect(allAccountedFor(ok, null)).toBe(false);
  });

  it('needs a reason and a note for non-productive hours, and a higher reading', () => {
    const errors = errorsOf(
      values({ reading: '1200', lines: [line('NON_PRODUCTIVE', '10', '', '')] }),
    );
    expect(errors).toContain('Choose the reason');
    expect(errors).toContain('Say what happened (a note is required for non-productive hours)');
    expect(errors).toContain('The new reading must be higher than the last one');
  });

  it('always sends a new reading and never a correction', () => {
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
      opening: false,
    });
    expect(fresh).not.toHaveProperty('corrects_report_id');
    expect(fresh).not.toHaveProperty('capture_id');
    expect(fresh.capture).toMatchObject({ id: 'cap9', kind: 'DAILY', reading: '1510.0' });
    expect(fresh.lines?.[1]).toEqual({
      kind: 'NON_PRODUCTIVE',
      reason_id: 'r1',
      hours: '180',
      note: 'Hose',
    });
    expect(fresh.opening).toBe(false);
    const opening = toReportPayload(v, {
      reportId: 'id3',
      machineId: 'm1',
      evidence,
      opening: true,
    });
    expect(opening).toMatchObject({ opening: true, lines: [] });
    expect(opening.capture).toMatchObject({ id: 'cap9', kind: 'DAILY', reading: '1510.0' });
    expect(() =>
      toReportPayload(v, {
        reportId: 'id4',
        machineId: 'm1',
        evidence: { ...evidence, gps: null },
        opening: false,
      }),
    ).toThrow();
  });
});

describe('report due', () => {
  it('follows the company reminder days, never-reported and first-reading machines', () => {
    expect(machineReportState({ ...STATUS, days_since_report: 2 }, 3)).toBe('UP_TO_DATE');
    expect(machineReportState({ ...STATUS, days_since_report: 3 }, 3)).toBe('DUE');
    expect(machineReportState({ ...STATUS, days_since_report: 30 }, null)).toBe('UP_TO_DATE');
    expect(machineReportState({ ...STATUS, days_since_report: null }, null)).toBe('DUE');
    expect(machineReportState({ ...STATUS, previous_reading: null }, 3)).toBe('DUE');
    expect(machineReportState({ ...STATUS, opening_required: true }, 3)).toBe('DUE');
    // A rejected report is final: the machine is due again.
    expect(machineReportState({ ...STATUS, rejected_report_id: 'r' }, 3)).toBe('DUE');
    expect(machineReportState({ ...STATUS, pending_report_id: 'p' }, 3)).toBe('AWAITING');
  });
});

describe('customer hours filled in when a customer is picked', () => {
  it('fills min(customer hours left, hours still to account for)', () => {
    // 10 h to account for; the customer has 4 h left → 4.
    expect(suggestedCustomerHours([emptyLine('CUSTOMER', '10')], 0, 'c1', '4', '10')).toBe('4');
    // Customer has 20 h; 4 h already on another line → the 6 h still to account for.
    const lines = [line('CUSTOMER', '4', 'c2'), emptyLine('CUSTOMER', '6')];
    expect(suggestedCustomerHours(lines, 1, 'c1', '20', '10')).toBe('6');
    // Hundredths are kept.
    expect(suggestedCustomerHours([emptyLine('CUSTOMER')], 0, 'c1', '1.15', '9')).toBe('1.15');
  });

  it("counts the customer's hours on other lines of the same report", () => {
    const lines = [line('CUSTOMER', '3', 'c1'), emptyLine('CUSTOMER', '7')];
    expect(suggestedCustomerHours(lines, 1, 'c1', '5', '10')).toBe('2');
    expect(customerHoursLeft(lines, 1, 'c1', '5')).toBe('2');
    // All their hours used by the other lines: nothing left, so they are not offered.
    expect(
      customerHoursLeft([line('CUSTOMER', '5', 'c1'), emptyLine('CUSTOMER')], 1, 'c1', '5'),
    ).toBeNull();
    expect(customerHoursLeft([], 0, 'c1', '0')).toBeNull();
  });

  it('leaves the line alone when nothing is left or the meter difference is unknown', () => {
    expect(
      suggestedCustomerHours(
        [line('CUSTOMER', '10', 'c2'), emptyLine('CUSTOMER')],
        1,
        'c1',
        '4',
        '10',
      ),
    ).toBeNull();
    expect(suggestedCustomerHours([emptyLine('CUSTOMER')], 0, 'c1', '4', null)).toBeNull();
  });

  it('replaces only hours the form filled in itself', () => {
    expect(hoursAreAuto(emptyLine('CUSTOMER', '10'))).toBe(true);
    expect(hoursAreAuto(emptyLine('CUSTOMER'))).toBe(true);
    expect(hoursAreAuto({ ...emptyLine('CUSTOMER', '10'), hours: '7' })).toBe(false);
    expect(hoursAreAuto({ ...emptyLine('CUSTOMER', '10'), hours: '' })).toBe(true);
  });
});
