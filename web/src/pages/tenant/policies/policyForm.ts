import { mixed, object, string } from 'yup';
import type { MachineDto, PolicyType, PolicyVersionIn } from '../../../api/types';
import {
  allowedFields,
  fromInputValue,
  inputError,
  POLICY_FIELDS,
  toInputValue,
  type OverrideScope,
} from './policyFields';

export interface FieldOverride {
  enabled: boolean;
  value: string;
}

export interface PolicyFormValues {
  policy_type: PolicyType;
  scope: OverrideScope;
  machine: MachineDto | null;
  site_id: string;
  /** UTC ISO instant or '' for "now". */
  effective_from: string;
  reason: string;
  overrides: Record<string, FieldOverride>;
}

export function initialPolicyValues(
  policyType: PolicyType,
  scope: OverrideScope,
  current: Record<string, unknown> | null,
  machine: MachineDto | null,
  siteId: string,
): PolicyFormValues {
  const overrides: Record<string, FieldOverride> = {};
  for (const def of POLICY_FIELDS[policyType]) {
    overrides[def.key] = { enabled: false, value: toInputValue(def, current?.[def.key]) };
  }
  return {
    policy_type: policyType,
    scope,
    machine,
    site_id: siteId,
    effective_from: '',
    reason: '',
    overrides,
  };
}

function isOverrideMap(value: unknown): value is Record<string, FieldOverride> {
  return typeof value === 'object' && value !== null;
}

interface FormParent {
  policy_type: PolicyType;
  scope: OverrideScope;
}

export const policyFormSchema = object({
  policy_type: mixed<PolicyType>()
    .oneOf(Object.keys(POLICY_FIELDS) as PolicyType[])
    .required(),
  scope: mixed<OverrideScope>().oneOf(['TENANT', 'MACHINE', 'SITE']).required(),
  machine: mixed<MachineDto>()
    .nullable()
    .defined()
    .test('machine', 'Select a machine', function (value) {
      return (this.parent as { scope: OverrideScope }).scope !== 'MACHINE' || value !== null;
    }),
  // Formik hands '' to Yup as undefined, hence the defaults.
  site_id: string()
    .default('')
    .test('site', 'Select a site', function (value) {
      return (this.parent as { scope: OverrideScope }).scope !== 'SITE' || value !== '';
    }),
  effective_from: string().default(''),
  reason: string()
    .trim()
    .required('Reason is required')
    .min(3, 'At least 3 characters')
    .max(1000, 'At most 1000 characters'),
  overrides: mixed<Record<string, FieldOverride>>(isOverrideMap)
    .required()
    .test('overrides', function (value) {
      const { policy_type, scope } = this.parent as FormParent;
      const fields = allowedFields(policy_type, scope);
      let enabled = 0;
      for (const def of fields) {
        const o = value[def.key];
        if (o?.enabled !== true) continue;
        enabled += 1;
        // Formik passes '' as undefined to Yup.
        const message = inputError(def, typeof o.value === 'string' ? o.value : '');
        if (message !== null) {
          return this.createError({ path: `overrides.${def.key}.value`, message });
        }
      }
      return enabled > 0 ? true : this.createError({ message: 'Override at least one field' });
    }),
});

/** Only enabled fields allowed for the scope are sent. */
export function toPolicyPayload(v: PolicyFormValues): PolicyVersionIn {
  const values: Record<string, unknown> = {};
  for (const def of allowedFields(v.policy_type, v.scope)) {
    const o = v.overrides[def.key];
    if (o?.enabled === true) values[def.key] = fromInputValue(def, o.value);
  }
  const scopeRef =
    v.scope === 'MACHINE' ? (v.machine?.id ?? null) : v.scope === 'SITE' ? v.site_id : null;
  return {
    scope: v.scope,
    scope_ref_id: scopeRef,
    values,
    reason: v.reason.trim(),
    effective_from: v.effective_from === '' ? null : v.effective_from,
  };
}
