import type {
  ContractDto,
  ContractIn,
  CustomerDto,
  CustomerIn,
  Page,
  RateCardDto,
  RateCardIn,
} from '../types';
import { contractSchema, customerSchema, rateCardSchema } from './jobSchemas';
import {
  tenantList,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

const customerPageSchema = tenantPageSchema(customerSchema);
const contractPageSchema = tenantPageSchema(contractSchema);

export const customerService = {
  /** GET /tenant/customers (listCustomers). */
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
  /** GET /tenant/contracts (listContracts). Filter: `customer_id`. */
  listContracts(query: TenantListQuery, signal?: AbortSignal): Promise<Page<ContractDto>> {
    return tenantPage('/tenant/contracts', contractPageSchema, query, 'contract page', signal);
  },
  /** POST /tenant/contracts (createContract). */
  createContract(body: ContractIn, idempotencyKey: string): Promise<ContractDto> {
    return tenantSend(
      'post',
      '/tenant/contracts',
      body,
      contractSchema,
      'contract',
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
};
