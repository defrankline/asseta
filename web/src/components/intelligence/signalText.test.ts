import { describe, expect, it } from 'vitest';
import type { CaseSourceType, RuleCode } from '../../api/types';
import { RULE_EVIDENCE } from '../../test/caseFixtures';
import {
  caseSignalLabel,
  explainCaseSignal,
  explainRiskSignal,
  NEUTRAL_SIGNAL_NOTICE,
  RULE_LABELS,
} from './signalText';

const TZ = 'Africa/Dar_es_Salaam';
const VERDICT = /fraud|guilty|cheat|theft|stole/i;

describe('explainRiskSignal', () => {
  it('UNREPORTED_ENGINE_ACTIVITY: minutes, local window, threshold and nearby jobs', () => {
    const text = explainRiskSignal(
      'UNREPORTED_ENGINE_ACTIVITY',
      RULE_EVIDENCE.UNREPORTED_ENGINE_ACTIVITY,
      TZ,
    );
    expect(text).toContain('ignition on');
    expect(text).toContain('recorded for 1 h 30 min,');
    expect(text).toContain('from 20 Oct 2026, 08:00 to 20 Oct 2026, 09:30');
    expect(text).toContain('threshold is 30 min');
    expect(text).toContain('J-1001');
    expect(text).not.toContain('still running');
  });

  it('UNREPORTED_ENGINE_ACTIVITY: long runs read as hours, not raw minutes', () => {
    const text = explainRiskSignal(
      'UNREPORTED_ENGINE_ACTIVITY',
      { ...RULE_EVIDENCE.UNREPORTED_ENGINE_ACTIVITY, uncovered_minutes: '1001.3' },
      TZ,
    );
    expect(text).toContain('recorded for 16 h 41 min,');
    expect(text).not.toContain('1001.3');
  });

  it('UNREPORTED_ENGINE_ACTIVITY: engine-hours basis and a run still going', () => {
    const text = explainRiskSignal(
      'UNREPORTED_ENGINE_ACTIVITY',
      {
        ...RULE_EVIDENCE.UNREPORTED_ENGINE_ACTIVITY,
        basis: 'ENGINE_HOURS',
        engine_hours_start: '100.5',
        engine_hours_end: '102',
        still_running_when_observed: true,
        running_jobs_nearby: [],
      },
      'UTC',
    );
    expect(text).toContain('engine hours rising from 100.5 to 102');
    expect(text).toContain('still running when observed');
    expect(text).not.toContain('Jobs on this machine');
  });

  it('DUPLICATE_RECEIPT: formatted money, short hash and the other expense', () => {
    const text = explainRiskSignal('DUPLICATE_RECEIPT', RULE_EVIDENCE.DUPLICATE_RECEIPT, 'UTC');
    expect(text).toContain('TZS 45,000.00');
    expect(text).toContain('SHA-256 abcdef012345…');
    expect(text).toContain('1 other expense incurred within 30 days');
    expect(text).toContain('incurred 18 Oct 2026, 09:00');
  });

  it('FUEL_ALLOWANCE_EXCEEDED: litres, meter hours, rate and allowance', () => {
    const text = explainRiskSignal(
      'FUEL_ALLOWANCE_EXCEEDED',
      RULE_EVIDENCE.FUEL_ALLOWANCE_EXCEEDED,
      'UTC',
    );
    expect(text).toContain('On job J-1002, 300 L of fuel were recorded over 10.0 meter hours');
    expect(text).toContain('30.000 L per meter hour against an allowance of 18 L per meter hour');
    expect(text).toContain('logged as used: 250 L');
  });

  it('EXPENSE_THRESHOLD_EXCEEDED: week, total, count and threshold as money', () => {
    const text = explainRiskSignal(
      'EXPENSE_THRESHOLD_EXCEEDED',
      RULE_EVIDENCE.EXPENSE_THRESHOLD_EXCEEDED,
      'UTC',
    );
    expect(text).toContain('week 2026-W43 total TZS 1,250,000.00 (3 expenses)');
    expect(text).toContain('weekly threshold of TZS 1,000,000.00');
  });

  it('CASH_NOT_HANDED_OVER: amount limit and time limit wording', () => {
    const amount = explainRiskSignal(
      'CASH_NOT_HANDED_OVER',
      RULE_EVIDENCE.CASH_NOT_HANDED_OVER,
      TZ,
    );
    expect(amount).toContain(
      'TZS 800,000.00 has been held in cash custody since 18 Oct 2026, 11:00',
    );
    expect(amount).toContain('(52.5 h)');
    expect(amount).toContain('limit for cash held is TZS 500,000.00');
    const time = explainRiskSignal(
      'CASH_NOT_HANDED_OVER',
      { ...RULE_EVIDENCE.CASH_NOT_HANDED_OVER, limit: 'HELD_LONGER_THAN_LIMIT' },
      TZ,
    );
    expect(time).toContain('handover within 48 h');
  });

  it('WORK_WITHOUT_AUTHORIZATION: record type, times and every reason', () => {
    const text = explainRiskSignal(
      'WORK_WITHOUT_AUTHORIZATION',
      RULE_EVIDENCE.WORK_WITHOUT_AUTHORIZATION,
      'UTC',
    );
    expect(text).toContain('A meter reading on job J-1003 dated 20 Oct 2026, 04:00');
    expect(text).toContain('before the job was approved (20 Oct 2026, 06:00)');
    expect(text).toContain('by a supervisor who was not assigned to the machine');
    expect(text).toContain('Clock tolerance: 15 min');
    const after = explainRiskSignal(
      'WORK_WITHOUT_AUTHORIZATION',
      {
        ...RULE_EVIDENCE.WORK_WITHOUT_AUTHORIZATION,
        record_type: 'EXPENSE',
        job_completed_at: '2026-10-19T17:00:00Z',
        reasons: ['AFTER_JOB_COMPLETED'],
      },
      'UTC',
    );
    expect(after).toContain('An expense on job J-1003');
    expect(after).toContain('after the job was completed (19 Oct 2026, 17:00)');
  });

  it('never states a verdict and tolerates missing evidence', () => {
    for (const code of Object.keys(RULE_LABELS) as RuleCode[]) {
      expect(explainRiskSignal(code, RULE_EVIDENCE[code], 'UTC')).not.toMatch(VERDICT);
      const empty = explainRiskSignal(code, {}, 'UTC');
      expect(empty).not.toMatch(VERDICT);
      expect(empty).not.toContain('undefined');
    }
    expect(NEUTRAL_SIGNAL_NOTICE).not.toMatch(VERDICT);
  });
});

describe('explainCaseSignal', () => {
  const of = (source_type: CaseSourceType, code: string, evidence: Record<string, unknown>) => ({
    source_type,
    code,
    evidence,
  });

  it('meter exceptions reuse the exception explanation and add the review state', () => {
    const s = of('METER_EXCEPTION', 'GPS_INACCURATE', {
      exception_status: 'CONFIRMED',
      blocking: true,
      accuracy_m: 80,
      max_accuracy_m: 25,
    });
    expect(caseSignalLabel(s)).toBe('GPS inaccurate');
    const text = explainCaseSignal(s, 'UTC');
    expect(text).toContain('Phone GPS accuracy was 80 m; the policy allows at most 25 m.');
    expect(text).toContain('A reviewer confirmed the discrepancy as recorded.');
    const open = explainCaseSignal(
      { ...s, evidence: { ...s.evidence, exception_status: 'OPEN' } },
      'UTC',
    );
    expect(open).toContain('blocks billing until reviewed');
  });

  it('tracking alerts, segregation-of-duties events and model outputs', () => {
    const alert = of('TRACKING_ALERT', 'TAMPER', {
      alert_title: 'Tracker case opened',
      alert_status: 'OPEN',
    });
    expect(caseSignalLabel(alert)).toBe('Tracker tamper signal');
    expect(explainCaseSignal(alert, 'UTC')).toContain(
      'Tracking alert "Tracker case opened" (Tracker tamper signal)',
    );
    const sod = of('SOD_EVENT', 'SEGREGATION_OF_DUTIES_ATTEMPT', {
      action: 'verify',
      entity_type: 'cash_handover',
      outcome: 'REFUSED',
    });
    expect(explainCaseSignal(sod, 'UTC')).toBe(
      'The system refused an attempt to verify a cash handover record by the person whose own ' +
        'record it was (segregation of duties).',
    );
    const prediction = of('PREDICTION', 'FUEL_MODEL', {});
    expect(explainCaseSignal(prediction, 'UTC')).toContain('not a finding');
    for (const s of [alert, sod, prediction]) {
      expect(explainCaseSignal(s, 'UTC')).not.toMatch(VERDICT);
    }
  });

  it('risk signals linked to a case use the rule title and sentence', () => {
    const s = of('RISK_SIGNAL', 'DUPLICATE_RECEIPT', { ...RULE_EVIDENCE.DUPLICATE_RECEIPT });
    expect(caseSignalLabel(s)).toBe(RULE_LABELS.DUPLICATE_RECEIPT);
    expect(explainCaseSignal(s, 'UTC')).toContain('TZS 45,000.00');
  });
});
