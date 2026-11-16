import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { EffectivePolicyView } from './EffectivePolicyView';
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
    expect(findField('EXPENSE_CAPTURE', 'fuel_enabled')?.kind).toBe('bool');
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

  it('hides retired keys an older stored version still carries', () => {
    renderWithProviders(
      <EffectivePolicyView
        policy={{
          policy_type: 'CUSTOMER_HOURS',
          values: { enabled: true, walk_in_standard_contract: true, some_new_key: 1 },
          version_stamp: 'v7',
        }}
      />,
    );
    expect(screen.queryByText('walk_in_standard_contract')).not.toBeInTheDocument();
    expect(screen.getAllByText('some_new_key')).not.toHaveLength(0);
  });
});
