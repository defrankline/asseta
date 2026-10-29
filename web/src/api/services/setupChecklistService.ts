import { array, object, type Schema } from 'yup';
import { apiClient } from '../client';
import type { components } from '../generated/schema';
import { parseResponse } from '../validation';
import { bool, int, nullableId, nullableInt, nullableText, oneOf, text } from './schemaKit';
import { seg, tenantGet, tenantSend } from './tenantRequest';

type Schemas = components['schemas'];
export type SetupChecklistDto = Schemas['SetupChecklistDto'];
export type SetupStepDto = Schemas['SetupStepDto'];
export type SetupCheckDto = Schemas['SetupCheckDto'];
export type SetupStepKey = Schemas['StepKey'];
export type SetupStepStatus = Schemas['StepStatus'];

export const SETUP_STEP_STATUSES: readonly SetupStepStatus[] = [
  'DONE',
  'TODO',
  'NOT_NEEDED',
  'NOT_APPLICABLE',
];

export const SETUP_STEP_KEYS: readonly SetupStepKey[] = [
  'COMPANY_SETTINGS',
  'PEOPLE',
  'MACHINE_TYPES_AND_RATES',
  'MACHINES',
  'TRACKERS',
  'SITES',
  'CUSTOMERS_AND_CONTRACTS',
  'CONTROLS_CHOSEN',
  'REASON_LISTS',
  'DEPOSIT_ACCOUNTS',
  'METER_BASELINES',
  'FIELD_APP_SIGNED_IN',
  'FIRST_JOB',
];

const checkSchema: Schema<SetupCheckDto> = object({
  key: text(),
  label: text(),
  done: bool(),
  optional: bool(),
  done_count: nullableInt(),
  total_count: nullableInt(),
  link: text(),
  required_permission: text(),
});

const notNeededFields = {
  reason: nullableText(),
  marked_by: text(),
  marked_by_name: nullableText().optional(),
  marked_at: text(),
};

const stepSchema: Schema<SetupStepDto> = object({
  key: oneOf(SETUP_STEP_KEYS),
  order: int(),
  title: text(),
  description: text(),
  status: oneOf(SETUP_STEP_STATUSES),
  done_count: nullableInt(),
  total_count: nullableInt(),
  link: text(),
  required_permission: text(),
  can_mark_not_needed: bool(),
  not_needed: object(notNeededFields).nullable().optional().default(undefined),
  checks: array(checkSchema).optional(),
});

const checklistSchema: Schema<SetupChecklistDto> = object({
  steps: array(stepSchema).required(),
  steps_done: int(),
  steps_total: int(),
  percent: int(),
  complete: bool(),
  dismissed: bool(),
  dismissed_by: nullableId().optional(),
  dismissed_by_name: nullableText().optional(),
  dismissed_at: nullableText().optional(),
  controls_confirmed_by: nullableId().optional(),
  controls_confirmed_by_name: nullableText().optional(),
  controls_confirmed_at: nullableText().optional(),
  as_of: text(),
});

const base = '/tenant/setup-checklist';
const WHAT = 'setup checklist';

async function tenantDelete(url: string, idempotencyKey: string): Promise<SetupChecklistDto> {
  const data = await apiClient.delete<unknown>(url, { tenantScoped: true, idempotencyKey });
  return parseResponse(checklistSchema, data, WHAT);
}

/** Go-live setup checklist: live per-tenant steps plus the owner's choices (not needed, confirm, hide). */
export const setupChecklistService = {
  /** GET /tenant/setup-checklist (getSetupChecklist). */
  get(signal?: AbortSignal): Promise<SetupChecklistDto> {
    return tenantGet(base, checklistSchema, WHAT, signal);
  },
  /** POST /tenant/setup-checklist/steps/{key}/not-needed (markSetupStepNotNeeded). */
  markNotNeeded(
    key: SetupStepKey,
    reason: string,
    idempotencyKey: string,
  ): Promise<SetupChecklistDto> {
    return tenantSend(
      'post',
      `${base}/steps/${seg(key)}/not-needed`,
      { reason },
      checklistSchema,
      WHAT,
      idempotencyKey,
    );
  },
  /** DELETE /tenant/setup-checklist/steps/{key}/not-needed (undoSetupStepNotNeeded). */
  undoNotNeeded(key: SetupStepKey, idempotencyKey: string): Promise<SetupChecklistDto> {
    return tenantDelete(`${base}/steps/${seg(key)}/not-needed`, idempotencyKey);
  },
  /** POST /tenant/setup-checklist/confirm-controls (confirmSetupControls). */
  confirmControls(note: string | null, idempotencyKey: string): Promise<SetupChecklistDto> {
    return tenantSend(
      'post',
      `${base}/confirm-controls`,
      { note },
      checklistSchema,
      WHAT,
      idempotencyKey,
    );
  },
  /** POST /tenant/setup-checklist/dismiss (dismissSetupChecklist): hide the banner for everyone. */
  dismiss(idempotencyKey: string): Promise<SetupChecklistDto> {
    return tenantSend('post', `${base}/dismiss`, {}, checklistSchema, WHAT, idempotencyKey);
  },
  /** DELETE /tenant/setup-checklist/dismiss (undismissSetupChecklist): show the banner again. */
  undismiss(idempotencyKey: string): Promise<SetupChecklistDto> {
    return tenantDelete(`${base}/dismiss`, idempotencyKey);
  },
};
