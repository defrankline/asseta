import { describe, expect, it } from 'vitest';
import { grantSchema, toGrantBody, type GrantFormValues } from './grantForm';

const valid: GrantFormValues = {
  tenant_id: '11111111-1111-4111-8111-111111111111',
  scope: 'OPERATIONS',
  starts_on: '2026-11-01',
  ends_on: '',
  consent_reference: '  LTR-889 ',
  notes: '',
};

async function errorsOf(values: GrantFormValues): Promise<string[]> {
  try {
    await grantSchema.validate(values, { abortEarly: false });
    return [];
  } catch (err) {
    return (err as { errors: string[] }).errors;
  }
}

describe('grant mandate form', () => {
  it('rejects an end date before the start date', async () => {
    expect(await errorsOf({ ...valid, ends_on: '2026-10-31' })).toEqual([
      'End date cannot be before the start date',
    ]);
  });

  it('accepts an open-ended mandate and an end date on or after the start', async () => {
    expect(await errorsOf(valid)).toEqual([]);
    expect(await errorsOf({ ...valid, ends_on: '2026-11-01' })).toEqual([]);
    expect(await errorsOf({ ...valid, ends_on: '2027-01-31' })).toEqual([]);
  });

  it('requires the client, start date and written consent reference', async () => {
    const errors = await errorsOf({
      ...valid,
      tenant_id: '',
      starts_on: '',
      consent_reference: ' ',
    });
    expect(errors).toEqual(
      expect.arrayContaining([
        'Client is required',
        'Start date is required',
        'Consent reference is required',
      ]),
    );
  });

  it('maps an empty end date to null and trims text', () => {
    expect(toGrantBody(valid)).toEqual({
      tenant_id: valid.tenant_id,
      scope: 'OPERATIONS',
      starts_on: '2026-11-01',
      ends_on: null,
      consent_reference: 'LTR-889',
      notes: '',
    });
  });
});
