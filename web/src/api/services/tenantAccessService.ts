import { array, boolean, object, string, type Schema } from 'yup';
import type {
  InviteIn,
  InviteResultDto,
  MemberDto,
  MemberNameIn,
  PasswordResetDto,
  TenantRoleDto,
} from '../types';
import { memberSchema } from './mandateSchemas';
import { seg, tenantList, tenantSend } from './tenantRequest';

const base = '/tenant/access';

const members = array(memberSchema).required();

const roleSchema: Schema<TenantRoleDto> = object({
  role_key: string().defined(),
  carries_approvals: boolean().required(),
});

const inviteResultSchema: Schema<InviteResultDto> = object({
  user_id: string().required(),
  created_account: boolean().required(),
  temporary_password: string().nullable().optional(),
});

const passwordSchema: Schema<PasswordResetDto> = object({
  temporary_password: string().required(),
});

/** Who the members list shows: people with a role now, deactivated people, or both. */
export type MemberListStatus = 'ACTIVE' | 'INACTIVE' | 'ALL';

/** Tenant users & roles (Keycloak authoritative; Asseta keeps an effective-dated mirror). */
export const tenantAccessService = {
  /** GET /tenant/access/members (listTenantMembers). */
  listMembers(status: MemberListStatus, signal?: AbortSignal): Promise<MemberDto[]> {
    return tenantList(`${base}/members`, memberSchema, 'members', signal, { status });
  },
  /** GET /tenant/access/roles (listTenantRoles): the roles that can be given. */
  listRoles(signal?: AbortSignal): Promise<TenantRoleDto[]> {
    return tenantList(`${base}/roles`, roleSchema, 'roles', signal);
  },
  /** POST /tenant/access/members: a new account gets a one-time password, shown once. */
  invite(body: InviteIn, idempotencyKey: string): Promise<InviteResultDto> {
    return tenantSend('post', `${base}/members`, body, inviteResultSchema, 'user', idempotencyKey);
  },
  /** POST /tenant/access/members/{user}/roles/{role} (grantTenantRole). */
  grantRole(userId: string, roleKey: string, idempotencyKey: string): Promise<MemberDto[]> {
    const url = `${base}/members/${seg(userId)}/roles/${seg(roleKey)}`;
    return tenantSend('post', url, {}, members, 'members', idempotencyKey);
  },
  /** POST /tenant/access/members/{user}/roles/{role}/revoke. MANDATE_MANAGED for mandate roles. */
  revokeRole(userId: string, roleKey: string, idempotencyKey: string): Promise<MemberDto[]> {
    const url = `${base}/members/${seg(userId)}/roles/${seg(roleKey)}/revoke`;
    return tenantSend('post', url, {}, members, 'members', idempotencyKey);
  },
  /** PUT /tenant/access/members/{user}/name. ACCOUNT_USED_ELSEWHERE when they also use another company. */
  rename(userId: string, body: MemberNameIn, idempotencyKey: string): Promise<MemberDto[]> {
    const url = `${base}/members/${seg(userId)}/name`;
    return tenantSend('put', url, body, members, 'members', idempotencyKey);
  },
  /** POST /tenant/access/members/{user}/deactivate. */
  deactivate(userId: string, idempotencyKey: string): Promise<MemberDto[]> {
    const url = `${base}/members/${seg(userId)}/deactivate`;
    return tenantSend('post', url, {}, members, 'members', idempotencyKey);
  },
  /** POST /tenant/access/members/{user}/reactivate: the roles they had come back. */
  reactivate(userId: string, idempotencyKey: string): Promise<MemberDto[]> {
    const url = `${base}/members/${seg(userId)}/reactivate`;
    return tenantSend('post', url, {}, members, 'members', idempotencyKey);
  },
  /** POST /tenant/access/members/{user}/reset-password: a one-time password, shown once. */
  resetPassword(userId: string, idempotencyKey: string): Promise<PasswordResetDto> {
    const url = `${base}/members/${seg(userId)}/reset-password`;
    return tenantSend('post', url, {}, passwordSchema, 'password', idempotencyKey);
  },
};
