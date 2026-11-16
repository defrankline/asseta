import type {
  CustomerDto,
  CustomerIn,
  CustomerUpdateIn,
  LifecycleChangeIn,
  Page,
  RateCardDto,
  RateCardIn,
} from '../types';
import { customerSchema, rateCardSchema } from './customerSchemas';
import {
  type TenantListQuery,
  seg,
  tenantGet,
  tenantLifecycle,
  tenantList,
  tenantPage,
  tenantPageSchema,
  tenantSend,
} from './tenantRequest';

const customerPageSchema = tenantPageSchema(customerSchema);
const cu = (id: string) => `/tenant/customers/${seg(id)}`;

export const customerService = {
  /** GET /tenant/customers (listCustomers). Filter: `include_inactive`. */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<CustomerDto>> {
    return tenantPage('/tenant/customers', customerPageSchema, query, 'customer page', signal);
  },
  /** POST /tenant/customers (createCustomer). */
  create(body: CustomerIn, idempotencyKey: string): Promise<CustomerDto> {
    return tenantSend(
      'post',
      '/tenant/customers',
      body,
      customerSchema,
      'customer',
      idempotencyKey,
    );
  },
  /** GET /tenant/rate-cards (listRateCards): every version, newest first. */
  listRateCards(machineCategoryId?: string, signal?: AbortSignal): Promise<RateCardDto[]> {
    return tenantList('/tenant/rate-cards', rateCardSchema, 'rate cards', signal, {
      machine_category_id: machineCategoryId,
    });
  },
  /** POST /tenant/rate-cards (createRateCard): always a new effective-dated version. */
  createRateCard(body: RateCardIn, idempotencyKey: string): Promise<RateCardDto> {
    return tenantSend(
      'post',
      '/tenant/rate-cards',
      body,
      rateCardSchema,
      'rate card',
      idempotencyKey,
    );
  },
  /** GET /tenant/customers/{id} (getCustomer). */
  get(customerId: string, signal?: AbortSignal): Promise<CustomerDto> {
    return tenantGet(cu(customerId), customerSchema, 'customer', signal);
  },
  /** PUT /tenant/customers/{id} (updateCustomer); `version` required. */
  update(customerId: string, body: CustomerUpdateIn, idempotencyKey: string): Promise<CustomerDto> {
    return tenantSend('put', cu(customerId), body, customerSchema, 'customer', idempotencyKey);
  },
  /** POST /tenant/customers/{id}/deactivate (deactivateCustomer). */
  deactivate(id: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return tenantLifecycle(
      `${cu(id)}/deactivate`,
      body,
      customerSchema,
      'customer',
      idempotencyKey,
    );
  },
  /** POST /tenant/customers/{id}/reactivate (reactivateCustomer). */
  reactivate(id: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return tenantLifecycle(
      `${cu(id)}/reactivate`,
      body,
      customerSchema,
      'customer',
      idempotencyKey,
    );
  },
};
