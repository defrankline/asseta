import type {
  CustomerBalanceDto,
  CustomerPaymentDto,
  CustomerPaymentIn,
  CustomerStatementDto,
  Page,
  ProfitabilityDto,
  ProfitabilityGroupBy,
  SettlementDecisionIn,
} from '../types';
import {
  customerBalanceSchema,
  customerPaymentSchema,
  customerStatementSchema,
  profitabilitySchema,
} from './financeSchemas';
import {
  seg,
  tenantGet,
  tenantList,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

const paymentPageSchema = tenantPageSchema(customerPaymentSchema);
const pay = (id: string) => `/tenant/customer-payments/${seg(id)}`;

/** Customer payments: CLAIMED on record, VERIFIED / REJECTED by someone else. */
export const customerPaymentService = {
  /** GET /tenant/customer-payments (listCustomerPayments). Filters: `status`, `customer_id`, `staff_member_id`. */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<CustomerPaymentDto>> {
    return tenantPage(
      '/tenant/customer-payments',
      paymentPageSchema,
      query,
      'customer payments',
      signal,
    );
  },
  /** GET /tenant/customer-payments/{id}. */
  get(paymentId: string, signal?: AbortSignal): Promise<CustomerPaymentDto> {
    return tenantGet(pay(paymentId), customerPaymentSchema, 'customer payment', signal);
  },
  /** POST /tenant/customer-payments (recordCustomerPayment). */
  record(body: CustomerPaymentIn, idempotencyKey: string): Promise<CustomerPaymentDto> {
    return tenantSend(
      'post',
      '/tenant/customer-payments',
      body,
      customerPaymentSchema,
      'customer payment',
      idempotencyKey,
    );
  },
  /** POST /tenant/customer-payments/{id}/decision (decideCustomerPayment); never by the recorder. */
  decide(paymentId: string, body: SettlementDecisionIn, idempotencyKey: string) {
    return tenantSend(
      'post',
      `${pay(paymentId)}/decision`,
      body,
      customerPaymentSchema,
      'customer payment',
      idempotencyKey,
    );
  },
};

export interface StatementQuery {
  from: string;
  to: string;
  currency?: string | undefined;
}

/** Customer receivables (per currency) and statements. */
export const receivablesService = {
  /** GET /tenant/customers/{id}/balance (getCustomerBalance): one row per currency. */
  balances(customerId: string, signal?: AbortSignal): Promise<CustomerBalanceDto[]> {
    return tenantList(
      `/tenant/customers/${seg(customerId)}/balance`,
      customerBalanceSchema,
      'customer balance',
      signal,
    );
  },
  /** GET /tenant/customers/{id}/statement (getCustomerStatement): one currency, tenant-local days. */
  statement(
    customerId: string,
    query: StatementQuery,
    signal?: AbortSignal,
  ): Promise<CustomerStatementDto> {
    return tenantGet(
      `/tenant/customers/${seg(customerId)}/statement`,
      customerStatementSchema,
      'customer statement',
      signal,
      { from: query.from, to: query.to, currency: query.currency },
    );
  },
};

export const profitabilityService = {
  /** GET /tenant/finance/profitability (getProfitability): rows per group and currency. */
  report(
    groupBy: ProfitabilityGroupBy,
    from: string,
    to: string,
    signal?: AbortSignal,
  ): Promise<ProfitabilityDto> {
    return tenantGet(
      '/tenant/finance/profitability',
      profitabilitySchema,
      'profitability',
      signal,
      {
        group_by: groupBy,
        from,
        to,
      },
    );
  },
};
