import { object, type Schema } from 'yup';
import type {
  DepositAccountDto,
  DepositAccountIn,
  DepositAccountType,
  DepositAccountUpdateIn,
} from '../custodyTypes';
import type { LifecycleChangeIn, Page } from '../types';
import { bool, id, int, nullableId, nullableText, oneOf, text } from './schemaKit';
import {
  seg,
  tenantGet,
  tenantLifecycle,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

export const DEPOSIT_ACCOUNT_TYPES: readonly DepositAccountType[] = [
  'BANK',
  'MOBILE_MONEY',
  'CASH_OFFICE',
];

/** A company account remittances are paid into; the number is stored masked ("•••• 4821"). */
export const depositAccountSchema: Schema<DepositAccountDto> = object({
  id: id(),
  name: text(),
  account_type: oneOf(DEPOSIT_ACCOUNT_TYPES),
  institution: nullableText(),
  account_number_masked: nullableText(),
  currency: text(),
  note: nullableText(),
  is_active: bool(),
  version: int(),
  created_at: text(),
  created_by: nullableId(),
  created_by_name: nullableText().optional(),
  updated_at: text(),
  deactivated_at: nullableText(),
  deactivated_by: nullableId(),
  deactivated_by_name: nullableText().optional(),
  deactivation_reason: nullableText(),
});

const depositAccountPage = tenantPageSchema(depositAccountSchema);
const base = '/tenant/deposit-accounts';
const one = (accountId: string) => `${base}/${seg(accountId)}`;

/** Company deposit accounts (DEC-031 D1): list / create / get / edit / deactivate / reactivate. */
export const depositAccountService = {
  /** GET /tenant/deposit-accounts (listDepositAccounts). Filters: `account_type`, `include_inactive`. */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<DepositAccountDto>> {
    return tenantPage(base, depositAccountPage, query, 'deposit accounts', signal);
  },
  /** POST /tenant/deposit-accounts (createDepositAccount). */
  create(body: DepositAccountIn, idempotencyKey: string): Promise<DepositAccountDto> {
    return tenantSend('post', base, body, depositAccountSchema, 'deposit account', idempotencyKey);
  },
  /** GET /tenant/deposit-accounts/{id} (getDepositAccount). */
  get(accountId: string, signal?: AbortSignal): Promise<DepositAccountDto> {
    return tenantGet(one(accountId), depositAccountSchema, 'deposit account', signal);
  },
  /** PATCH /tenant/deposit-accounts/{id} (updateDepositAccount) with the `version` that was read. */
  update(
    accountId: string,
    body: DepositAccountUpdateIn,
    idempotencyKey: string,
  ): Promise<DepositAccountDto> {
    return tenantSend(
      'patch',
      one(accountId),
      body,
      depositAccountSchema,
      'deposit account',
      idempotencyKey,
    );
  },
  /** POST /tenant/deposit-accounts/{id}/deactivate (deactivateDepositAccount). */
  deactivate(accountId: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return tenantLifecycle(
      `${one(accountId)}/deactivate`,
      body,
      depositAccountSchema,
      'deposit account',
      idempotencyKey,
    );
  },
  /** POST /tenant/deposit-accounts/{id}/reactivate (reactivateDepositAccount). */
  reactivate(accountId: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return tenantLifecycle(
      `${one(accountId)}/reactivate`,
      body,
      depositAccountSchema,
      'deposit account',
      idempotencyKey,
    );
  },
};
