import { array } from 'yup';
import type { MemberDto } from '../types';
import { memberSchema } from './mandateSchemas';
import { seg, tenantList, tenantSend } from './tenantRequest';

const base = '/tenant/access';

/** Tenant users & roles (Keycloak group membership mirror). */
export const tenantAccessService = {
  /** GET /tenant/access/members (listTenantMembers). */
  listMembers(signal?: AbortSignal): Promise<MemberDto[]> {
    return tenantList(`${base}/members`, memberSchema, 'members', signal);
  },
  /** POST /tenant/access/members/{user}/roles/{role}/revoke. MANDATE_MANAGED for mandate roles. */
  revokeRole(userId: string, roleKey: string, idempotencyKey: string): Promise<MemberDto[]> {
    return tenantSend(
      'post',
      `${base}/members/${seg(userId)}/roles/${seg(roleKey)}/revoke`,
      {},
      array(memberSchema).required(),
      'members',
      idempotencyKey,
    );
  },
};
