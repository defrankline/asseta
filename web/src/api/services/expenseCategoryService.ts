import type {
  ExpenseCategoryDto,
  ExpenseCategoryIn,
  ExpenseCategoryUpdateIn,
  LifecycleChangeIn,
} from '../types';
import { expenseCategorySchema } from './expenseSchemas';
import {
  inactiveParam,
  seg,
  tenantGet,
  tenantLifecycle,
  tenantList,
  tenantSend,
} from './tenantRequest';

const base = '/tenant/expense-categories';
const one = (id: string) => `${base}/${seg(id)}`;
const WHAT = 'expense category';

export const expenseCategoryService = {
  /** GET /tenant/expense-categories (listExpenseCategories); `q` searches code and name. */
  list(signal?: AbortSignal, q?: string, includeInactive?: boolean): Promise<ExpenseCategoryDto[]> {
    return tenantList(base, expenseCategorySchema, 'expense categories', signal, {
      q,
      ...inactiveParam(includeInactive),
    });
  },
  /** GET /tenant/expense-categories/{id} (getExpenseCategory). */
  get(categoryId: string, signal?: AbortSignal): Promise<ExpenseCategoryDto> {
    return tenantGet(one(categoryId), expenseCategorySchema, WHAT, signal);
  },
  /** POST /tenant/expense-categories (createExpenseCategory). */
  create(body: ExpenseCategoryIn, idempotencyKey: string): Promise<ExpenseCategoryDto> {
    return tenantSend('post', base, body, expenseCategorySchema, WHAT, idempotencyKey);
  },
  /** PUT /tenant/expense-categories/{id} (updateExpenseCategory); `version` required. */
  update(
    categoryId: string,
    body: ExpenseCategoryUpdateIn,
    idempotencyKey: string,
  ): Promise<ExpenseCategoryDto> {
    return tenantSend('put', one(categoryId), body, expenseCategorySchema, WHAT, idempotencyKey);
  },
  /** POST /tenant/expense-categories/{id}/deactivate (deactivateExpenseCategory). */
  deactivate(
    categoryId: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ): Promise<ExpenseCategoryDto> {
    return tenantLifecycle(
      `${one(categoryId)}/deactivate`,
      body,
      expenseCategorySchema,
      WHAT,
      idempotencyKey,
    );
  },
  /** POST /tenant/expense-categories/{id}/reactivate (reactivateExpenseCategory). */
  reactivate(
    categoryId: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ): Promise<ExpenseCategoryDto> {
    return tenantLifecycle(
      `${one(categoryId)}/reactivate`,
      body,
      expenseCategorySchema,
      WHAT,
      idempotencyKey,
    );
  },
};
