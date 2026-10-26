import type { EffectivePolicyDto, PolicyType, PolicyVersionDto, PolicyVersionIn } from '../types';
import { effectivePolicySchema, policyVersionSchema } from './geoSchemas';
import { seg, tenantGet, tenantList, tenantSend } from './tenantRequest';

export interface EffectivePolicyQuery {
  machine_id?: string | undefined;
  site_id?: string | undefined;
  /** STAFF scope (e.g. a custodian's cash holding allowance). */
  staff_id?: string | undefined;
  /** MACHINE_CATEGORY scope (e.g. the fuel norm of a machine category). */
  category_id?: string | undefined;
  at?: string | undefined;
}

const base = (ptype: PolicyType) => `/tenant/policies/${seg(ptype)}`;

export const policyService = {
  /** GET /tenant/policies/{ptype}/effective (getEffectivePolicy). */
  effective(
    ptype: PolicyType,
    query: EffectivePolicyQuery,
    signal?: AbortSignal,
  ): Promise<EffectivePolicyDto> {
    return tenantGet(
      `${base(ptype)}/effective`,
      effectivePolicySchema,
      'effective policy',
      signal,
      {
        machine_id: query.machine_id,
        site_id: query.site_id,
        staff_id: query.staff_id,
        category_id: query.category_id,
        at: query.at,
      },
    );
  },
  /** GET /tenant/policies/{ptype}/versions (listPolicyVersions). */
  versions(ptype: PolicyType, signal?: AbortSignal): Promise<PolicyVersionDto[]> {
    return tenantList(`${base(ptype)}/versions`, policyVersionSchema, 'policy versions', signal);
  },
  /** POST /tenant/policies/{ptype}/versions (createTenantPolicyVersion). */
  create(
    ptype: PolicyType,
    body: PolicyVersionIn,
    idempotencyKey: string,
  ): Promise<PolicyVersionDto> {
    return tenantSend(
      'post',
      `${base(ptype)}/versions`,
      body,
      policyVersionSchema,
      'policy version',
      idempotencyKey,
    );
  },
};
