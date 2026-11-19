import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { PolicyVersionsTable } from './PolicyVersionsTable';
import { parseHoursPolicy } from '../hours/useHoursPolicy';
import { findField, formatPolicyValue, inputError } from './policyFields';

describe('ADR-008 policy fields', () => {
  it('offers field credit sales, the report hours scope and the report reminder', () => {
    expect(findField('CUSTOMER_HOURS', 'field_credit_sales')?.kind).toBe('bool');
    const scope = findField('CUSTOMER_HOURS', 'report_hours_scope');
    if (scope === undefined) throw new Error('report_hours_scope missing');
    expect(formatPolicyValue(scope, 'CUSTOMER')).toBe('Any of the customer’s hours');
    expect(formatPolicyValue(scope, 'MACHINE')).toBe(
      'Only the customer’s hours on the reported machine',
    );
    expect(inputError(scope, 'SITE')).not.toBeNull();
    const reminder = findField('CUSTOMER_HOURS', 'machine_report_reminder_days');
    expect(reminder).toMatchObject({ kind: 'nullableNumber', unit: 'days' });
    const visitGap = findField('CUSTOMER_HOURS', 'visit_gap_warning_hours');
    if (visitGap === undefined) throw new Error('visit_gap_warning_hours missing');
    expect(visitGap).toMatchObject({
      kind: 'nullableNumber',
      label: "Warn when a machine wasn't visited for (hours)",
    });
    expect(inputError(visitGap, '')).toBeNull();
    expect(inputError(visitGap, '48')).toBeNull();
    expect(inputError(visitGap, 'two days')).not.toBeNull();
    expect(findField('EXPENSE_CAPTURE', 'fuel_enabled')?.kind).toBe('bool');
  });

  it('reads the visit-gap warning: 24 h by default, null for no warning', () => {
    expect(parseHoursPolicy({}).visitGapWarningHours).toBe(24);
    expect(parseHoursPolicy({ visit_gap_warning_hours: 48 }).visitGapWarningHours).toBe(48);
    expect(parseHoursPolicy({ visit_gap_warning_hours: null }).visitGapWarningHours).toBeNull();
  });

  it('no longer offers the retired job, booking, check-in and unbilled settings', () => {
    for (const key of [
      'walk_in_standard_contract',
      'prepaid_job_auto_approval',
      'billing_modes',
      'drawdown',
      'over_consumption',
    ]) {
      expect(findField('CUSTOMER_HOURS', key)).toBeUndefined();
    }
    for (const key of ['site_checkin_required', 'site_checkin_times', 'unbilled_after_days']) {
      expect(findField('OVERSIGHT', key)).toBeUndefined();
    }
  });

  it('no longer offers the retired reading, risk, engine-hour and reversal settings', () => {
    expect(findField('METER_CAPTURE', 'opening_mode')).toBeUndefined();
    expect(findField('METER_CAPTURE', 'closing_mode')).toBeUndefined();
    expect(findField('METER_CAPTURE', 'capture_mode')?.kind).toBe('enum');
    expect(findField('FRAUD_CONTROLS', 'engine_activity_min_minutes')).toBeUndefined();
    expect(findField('FRAUD_CONTROLS', 'engine_without_work_case_min_minutes')).toBeUndefined();
    expect(findField('ENGINE_HOURS', 'baseline_required_before_start')).toBeUndefined();
    expect(findField('ENGINE_HOURS', 'prevent_overlapping_activity')).toBeUndefined();
    expect(findField('CUSTOMER_HOURS', 'reversal_used_hours_treatment')).toBeUndefined();
  });

  it('shows an older stored version in today’s names, without its retired keys', () => {
    const stored = (policy_type: 'CUSTOMER_HOURS' | 'METER_CAPTURE', values: object) => ({
      id: policy_type,
      policy_type,
      scope: 'TENANT' as const,
      scope_ref_id: null,
      version: 3,
      effective_from: '2026-10-01T00:00:00Z',
      values: values as Record<string, unknown>,
      reason: 'Older settings',
      created_at: '2026-10-01T00:00:00Z',
    });
    renderWithProviders(
      <PolicyVersionsTable
        versions={[
          stored('CUSTOMER_HOURS', { walk_in_standard_contract: true, some_new_key: 1 }),
          stored('METER_CAPTURE', { opening_mode: 'AUTOMATIC', closing_mode: 'MANUAL' }),
        ]}
        timeZone="UTC"
        refLabel={(id) => id}
      />,
    );
    expect(screen.queryByText(/walk_in_standard_contract/)).not.toBeInTheDocument();
    expect(screen.getByText(/some_new_key/)).toBeInTheDocument();
    expect(screen.queryByText(/opening_mode|Opening/)).not.toBeInTheDocument();
    expect(screen.getByText('Reading mode: Manual (numeric entry)')).toBeInTheDocument();
  });
});
