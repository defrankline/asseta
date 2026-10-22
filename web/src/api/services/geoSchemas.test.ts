import { describe, expect, it } from 'vitest';
import { parseResponse } from '../validation';
import { POLICY_TYPES, effectivePolicySchema, policyVersionSchema } from './geoSchemas';

describe('policy schemas', () => {
  it.each(POLICY_TYPES)('accept an effective %s policy and its versions', (policyType) => {
    const effective = { policy_type: policyType, version_stamp: `${policyType}@P1`, values: {} };
    expect(parseResponse(effectivePolicySchema, effective, 'effective policy')).toEqual(effective);
    const version = {
      id: '11111111-1111-4111-8111-111111111111',
      policy_type: policyType,
      scope: 'TENANT',
      scope_ref_id: null,
      version: 1,
      effective_from: '2026-10-22T00:00:00Z',
      values: { a: 1 },
      reason: 'test',
      created_at: '2026-10-22T00:00:00Z',
    };
    expect(parseResponse(policyVersionSchema, version, 'policy version')).toEqual(version);
  });

  it('covers every policy type the meter-capture console needs and rejects unknown ones', () => {
    expect(POLICY_TYPES).toContain('METER_CAPTURE');
    expect(() =>
      parseResponse(
        effectivePolicySchema,
        { policy_type: 'NOPE', version_stamp: 'x', values: {} },
        'effective policy',
      ),
    ).toThrow('unexpected effective policy payload');
  });
});
