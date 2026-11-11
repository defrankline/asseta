import { describe, expect, it } from 'vitest';
import { findField, formatPolicyValue, inputError } from './policyFields';

describe('CUSTOMER_HOURS sale booking and cash activation fields', () => {
  it('offers the walk-in contract and prepaid auto-approval switches', () => {
    expect(findField('CUSTOMER_HOURS', 'walk_in_standard_contract')).toMatchObject({
      kind: 'bool',
      label: 'Walk-in customers get a standard rate-card contract with their first sale',
    });
    expect(findField('CUSTOMER_HOURS', 'prepaid_job_auto_approval')).toMatchObject({
      kind: 'bool',
      label:
        'Prepaid jobs booked with a sale are approved automatically once the sale is fully paid and verified',
    });
  });

  it('labels when cash counts as verified and accepts only the listed values', () => {
    const field = findField('CUSTOMER_HOURS', 'cash_activation');
    if (field === undefined) throw new Error('cash_activation missing');
    expect(field.kind).toBe('enum');
    expect(field.label).toBe('When cash on an hours sale counts as verified');
    expect(formatPolicyValue(field, 'VERIFY')).toBe('By the office (Verify)');
    expect(formatPolicyValue(field, 'ON_HANDOVER')).toBe('When the handover is confirmed');
    expect(formatPolicyValue(field, 'ON_RECORDING')).toBe('When recorded');
    expect(inputError(field, 'ON_HANDOVER')).toBeNull();
    expect(inputError(field, 'LATER')).not.toBeNull();
  });
});
