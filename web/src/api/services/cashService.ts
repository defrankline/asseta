import type {
  CashCollectionIn,
  CashCustodyBalanceDto,
  CashCustodyEntryDto,
  CashFloatIn,
  CashHandoverDto,
  CashHandoverIn,
  CashReconciliationDto,
  CashSupervisorSummaryDto,
  CustomerPaymentDto,
  Page,
  SettlementDecisionIn,
} from '../types';
import {
  custodyBalanceSchema,
  custodyEntrySchema,
  customerPaymentSchema,
  handoverSchema,
  reconciliationSchema,
  supervisorSummarySchema,
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

const handoverPageSchema = tenantPageSchema(handoverSchema);
const paymentPageSchema = tenantPageSchema(customerPaymentSchema);

export interface SupervisorSummaryQuery {
  from: string;
  to: string;
  currency?: string | undefined;
}

export interface ReconciliationQuery {
  staffMemberId: string;
  from: string;
  to: string;
  currency?: string | undefined;
}

/** Supervisor cash custody: floats, collections, handovers and daily reconciliation. */
export const cashService = {
  /** GET /tenant/cash/custody (getCashCustody): one balance per currency for a staff member. */
  custody(staffMemberId: string, signal?: AbortSignal): Promise<CashCustodyBalanceDto[]> {
    return tenantList('/tenant/cash/custody', custodyBalanceSchema, 'cash custody', signal, {
      staff_member_id: staffMemberId,
    });
  },
  /** GET /tenant/cash/custody/me (getMyCashCustody): the caller's balance per currency. */
  myCustody(signal?: AbortSignal): Promise<CashCustodyBalanceDto[]> {
    return tenantList('/tenant/cash/custody/me', custodyBalanceSchema, 'my cash custody', signal);
  },
  /** GET /tenant/cash/custody/me/reconciliation (getMyCashReconciliation): one per currency (`date` = tenant day). */
  myReconciliation(
    date: string | undefined,
    signal?: AbortSignal,
  ): Promise<CashReconciliationDto[]> {
    return tenantList(
      '/tenant/cash/custody/me/reconciliation',
      reconciliationSchema,
      'my reconciliation',
      signal,
      { date },
    );
  },
  /** GET /tenant/cash/custody/me/collections (listMyCashCollections). Filter: `status`. */
  myCollections(query: TenantListQuery, signal?: AbortSignal): Promise<Page<CustomerPaymentDto>> {
    return tenantPage(
      '/tenant/cash/custody/me/collections',
      paymentPageSchema,
      query,
      'my collections',
      signal,
    );
  },
  /** GET /tenant/cash/custody/me/handovers (listMyCashHandovers). Filter: `status`. */
  myHandovers(query: TenantListQuery, signal?: AbortSignal): Promise<Page<CashHandoverDto>> {
    return tenantPage(
      '/tenant/cash/custody/me/handovers',
      handoverPageSchema,
      query,
      'my handovers',
      signal,
    );
  },
  /** POST /tenant/cash/floats (issueCashFloat): opening balance or float issued. */
  issueFloat(body: CashFloatIn, idempotencyKey: string): Promise<CashCustodyEntryDto> {
    return tenantSend(
      'post',
      '/tenant/cash/floats',
      body,
      custodyEntrySchema,
      'cash float',
      idempotencyKey,
    );
  },
  /** POST /tenant/cash/collections (recordCashCollection): a CASH customer payment, CLAIMED. */
  recordCollection(body: CashCollectionIn, idempotencyKey: string): Promise<CustomerPaymentDto> {
    return tenantSend(
      'post',
      '/tenant/cash/collections',
      body,
      customerPaymentSchema,
      'cash collection',
      idempotencyKey,
    );
  },
  /** GET /tenant/cash/handovers (listCashHandovers). Filters: `status`, `staff_member_id`. */
  listHandovers(query: TenantListQuery, signal?: AbortSignal): Promise<Page<CashHandoverDto>> {
    return tenantPage('/tenant/cash/handovers', handoverPageSchema, query, 'handovers', signal);
  },
  /** POST /tenant/cash/handovers (recordCashHandover): CLAIMED until the office verifies it. */
  recordHandover(body: CashHandoverIn, idempotencyKey: string): Promise<CashHandoverDto> {
    return tenantSend(
      'post',
      '/tenant/cash/handovers',
      body,
      handoverSchema,
      'cash handover',
      idempotencyKey,
    );
  },
  /** POST /tenant/cash/handovers/{id}/decision (decideCashHandover); never by the recorder. */
  decideHandover(handoverId: string, body: SettlementDecisionIn, idempotencyKey: string) {
    return tenantSend(
      'post',
      `/tenant/cash/handovers/${seg(handoverId)}/decision`,
      body,
      handoverSchema,
      'cash handover',
      idempotencyKey,
    );
  },
  /** GET /tenant/cash/supervisor-summary (listCashSupervisorSummaries): every custodian x currency. */
  supervisorSummary(
    query: SupervisorSummaryQuery,
    signal?: AbortSignal,
  ): Promise<CashSupervisorSummaryDto[]> {
    return tenantList(
      '/tenant/cash/supervisor-summary',
      supervisorSummarySchema,
      'supervisor cash summary',
      signal,
      { from: query.from, to: query.to, currency: query.currency },
    );
  },
  /** GET /tenant/cash/reconciliation (getCashReconciliation): tenant-local days for one currency. */
  reconciliation(query: ReconciliationQuery, signal?: AbortSignal): Promise<CashReconciliationDto> {
    return tenantGet(
      '/tenant/cash/reconciliation',
      reconciliationSchema,
      'reconciliation',
      signal,
      {
        staff_member_id: query.staffMemberId,
        from: query.from,
        to: query.to,
        currency: query.currency,
      },
    );
  },
};
