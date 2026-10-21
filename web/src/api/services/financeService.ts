import type {
  CustomerBalanceDto,
  CustomerPaymentDto,
  CustomerPaymentIn,
  CustomerStatementDto,
  HireAllocateIn,
  HireInvoiceDraftIn,
  HireInvoiceDto,
  HireInvoiceIssueIn,
  HireInvoiceVoidIn,
  Page,
  ProfitabilityDto,
  ProfitabilityGroupBy,
  SettlementDecisionIn,
} from '../types';
import {
  customerBalanceSchema,
  customerPaymentSchema,
  customerStatementSchema,
  hireInvoiceSchema,
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

const invoicePageSchema = tenantPageSchema(hireInvoiceSchema);
const paymentPageSchema = tenantPageSchema(customerPaymentSchema);
const inv = (id: string) => `/tenant/hire-invoices/${seg(id)}`;
const pay = (id: string) => `/tenant/customer-payments/${seg(id)}`;

/** Tenant customer hire invoices (never the platform subscription invoices). */
export const hireInvoiceService = {
  /** GET /tenant/hire-invoices (listHireInvoices). Filters: `status`, `customer_id`; `q` = invoice number. */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<HireInvoiceDto>> {
    return tenantPage('/tenant/hire-invoices', invoicePageSchema, query, 'hire invoices', signal);
  },
  /** GET /tenant/hire-invoices/{id} (getHireInvoice). */
  get(invoiceId: string, signal?: AbortSignal): Promise<HireInvoiceDto> {
    return tenantGet(inv(invoiceId), hireInvoiceSchema, 'hire invoice', signal);
  },
  /** POST /tenant/hire-invoices (createHireInvoiceDraft): charges come verbatim from job summaries. */
  createDraft(body: HireInvoiceDraftIn, idempotencyKey: string): Promise<HireInvoiceDto> {
    return tenantSend(
      'post',
      '/tenant/hire-invoices',
      body,
      hireInvoiceSchema,
      'hire invoice',
      idempotencyKey,
    );
  },
  /** POST /tenant/hire-invoices/{id}/issue (issueHireInvoice): numbered, immutable snapshot. */
  issue(invoiceId: string, body: HireInvoiceIssueIn, idempotencyKey: string) {
    return tenantSend(
      'post',
      `${inv(invoiceId)}/issue`,
      body,
      hireInvoiceSchema,
      'hire invoice',
      idempotencyKey,
    );
  },
  /** POST /tenant/hire-invoices/{id}/void (voidHireInvoice): reversal adjustment, jobs released. */
  void(invoiceId: string, body: HireInvoiceVoidIn, idempotencyKey: string) {
    return tenantSend(
      'post',
      `${inv(invoiceId)}/void`,
      body,
      hireInvoiceSchema,
      'hire invoice',
      idempotencyKey,
    );
  },
};

/** Customer payments: CLAIMED on record, VERIFIED / REJECTED by someone else; allocations. */
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
  /** POST /tenant/customer-payments/{id}/allocations (allocateCustomerPayment). */
  allocate(paymentId: string, body: HireAllocateIn, idempotencyKey: string) {
    return tenantSend(
      'post',
      `${pay(paymentId)}/allocations`,
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
