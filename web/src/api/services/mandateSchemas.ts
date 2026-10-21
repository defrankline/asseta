/**
 * Runtime (Yup) response schemas for managed-service mandates and tenant access. Each schema is
 * annotated with its generated contract type, so contract drift fails `npm run typecheck`.
 */
import { array, object, string, type Schema } from 'yup';
import type {
  AssignableRoleDto,
  ClientMandateDto,
  MandateActionDto,
  MandateAssignmentDto,
  MandateDetailDto,
  MandateDto,
  MandateScope,
  MandateStatus,
  MemberDto,
  MemberRoleDto,
  PlatformStaffDto,
} from '../types';
import { bool, id, idList, int, nullableText, oneOf, text } from './schemaKit';

export const MANDATE_SCOPES: readonly MandateScope[] = ['FULL', 'OPERATIONS'];
export const MANDATE_STATUSES: readonly MandateStatus[] = [
  'IN_FORCE',
  'SCHEDULED',
  'EXPIRED',
  'REVOKED',
  'ENDED',
];

const mandateBadgeFields = {
  mandate_id: id(),
  reference: text(),
  scope: text(),
  ends_on: nullableText(),
};

/** Optional `mandate` badge on a /me tenant entry (absent or null for ordinary members). */
export const optionalMandateBadge = () =>
  object(mandateBadgeFields).nullable().optional().default(undefined);

const mandateFields = {
  id: id(),
  reference: text(),
  tenant_id: id(),
  tenant_name: text(),
  scope: oneOf(MANDATE_SCOPES),
  starts_on: text(),
  ends_on: nullableText(),
  consent_reference: text(),
  notes: text(),
  // Typed as a plain string by the contract; unknown values render as a neutral chip.
  status: text(),
  version: int(),
  granted_by: text(),
  granted_at: text(),
  closed_by: nullableText(),
  closed_at: nullableText(),
  close_reason: nullableText(),
  active_staff: int(),
};

export const mandateSchema: Schema<MandateDto> = object(mandateFields);

export const mandateAssignmentSchema: Schema<MandateAssignmentDto> = object({
  id: id(),
  user_id: id(),
  email: text(),
  display_name: text(),
  role_key: text(),
  assigned_at: text(),
  removed_at: nullableText(),
  is_active: bool(),
});

const mandateDetailFields = {
  ...mandateFields,
  assignments: array(mandateAssignmentSchema).required(),
};

export const mandateDetailSchema: Schema<MandateDetailDto> = object(mandateDetailFields);

export const platformStaffSchema: Schema<PlatformStaffDto> = object({
  user_id: id(),
  email: text(),
  display_name: text(),
});

export const assignableRoleSchema: Schema<AssignableRoleDto> = object({
  key: text(),
  permissions: idList(),
});

const mandateActionSchema: Schema<MandateActionDto> = object({
  occurred_at: text(),
  actor: text(),
  action: text(),
  entity_type: text(),
  entity_id: text(),
});

export const clientMandateSchema: Schema<ClientMandateDto> = object({
  mandate: object(mandateDetailFields).nullable().defined().default(null),
  recent_actions: array(mandateActionSchema).required(),
});

const memberRoleSchema: Schema<MemberRoleDto> = object({
  role_key: text(),
  since: text(),
  mandate_reference: string().nullable().optional(),
});

export const memberSchema: Schema<MemberDto> = object({
  user_id: id(),
  email: text(),
  display_name: text(),
  roles: array(memberRoleSchema).required(),
});
