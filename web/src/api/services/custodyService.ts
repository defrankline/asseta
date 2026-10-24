import { apiClient } from '../client';
import type { CashCustodyEntryDto, CashHandoverDto, LifecycleChangeIn, Page } from '../types';
import type {
  CashAcknowledgementIn,
  CashDecisionIn,
  CashReasonDto,
  CashReasonIn,
  CashReasonUpdateIn,
  CashRetentionDto,
  CashRetentionIn,
  CashTransferDto,
  CashTransferIn,
  CashVarianceDto,
  CustodianDto,
  CustodyAdjustmentDto,
  CustodyAdjustmentIn,
  CustodyTransactionDto,
  ReconciliationFigure,
  RemittanceDecisionIn,
  VarianceResolutionIn,
  WriteOffProposalIn,
} from '../custodyTypes';
import { parseResponse } from '../validation';
import {
  adjustmentSchema,
  custodianSchema,
  custodyTransactionSchema,
  reasonSchema,
  retentionSchema,
  transferSchema,
  varianceSchema,
} from './custodySchemas';
import { custodyEntrySchema, handoverSchema } from './financeSchemas';
import {
  seg,
  tenantGet,
  tenantLifecycle,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

const base = '/tenant/cash';
const custodianPage = tenantPageSchema(custodianSchema);
const transferPage = tenantPageSchema(transferSchema);
const floatPage = tenantPageSchema(custodyEntrySchema);
const variancePage = tenantPageSchema(varianceSchema);
const retentionPage = tenantPageSchema(retentionSchema);
const adjustmentPage = tenantPageSchema(adjustmentSchema);
const reasonPage = tenantPageSchema(reasonSchema);
const transactionPage = tenantPageSchema(custodyTransactionSchema);

export interface TransactionsQuery {
  /** Omitted: the caller's own custody (field work). */
  staffMemberId?: string | undefined;
  from: string;
  to: string;
  currency?: string | undefined;
  figure?: ReconciliationFigure | undefined;
  page: number;
  page_size: number;
}

/** Cash custody chain controls (design C): custodians, transfers, floats, variances, retentions, adjustments. */
export const custodyService = {
  /** GET /tenant/cash/custodians (listCashCustodians): any staff member who can hold cash; `q` = name/code. */
  custodians(query: TenantListQuery, signal?: AbortSignal): Promise<Page<CustodianDto>> {
    return tenantPage(`${base}/custodians`, custodianPage, query, 'custodians', signal);
  },

  /** GET /tenant/cash/transfers (listCashTransfers). Filters: `status`, `staff_member_id`. */
  transfers(query: TenantListQuery, signal?: AbortSignal): Promise<Page<CashTransferDto>> {
    return tenantPage(`${base}/transfers`, transferPage, query, 'cash transfers', signal);
  },
  /** GET /tenant/cash/transfers/{id} (getCashTransfer). */
  transfer(transferId: string, signal?: AbortSignal): Promise<CashTransferDto> {
    return tenantGet(
      `${base}/transfers/${seg(transferId)}`,
      transferSchema,
      'cash transfer',
      signal,
    );
  },
  /** POST /tenant/cash/transfers (recordCashTransfer): field-to-field, never a company receipt. */
  recordTransfer(body: CashTransferIn, idempotencyKey: string): Promise<CashTransferDto> {
    return tenantSend(
      'post',
      `${base}/transfers`,
      body,
      transferSchema,
      'cash transfer',
      idempotencyKey,
    );
  },
  /** POST /tenant/cash/transfers/{id}/acknowledgement (acknowledgeCashTransfer); never the sender. */
  acknowledgeTransfer(
    transferId: string,
    body: CashAcknowledgementIn,
    idempotencyKey: string,
  ): Promise<CashTransferDto> {
    return tenantSend(
      'post',
      `${base}/transfers/${seg(transferId)}/acknowledgement`,
      body,
      transferSchema,
      'cash transfer',
      idempotencyKey,
    );
  },

  /** GET /tenant/cash/floats (listCashFloats). Filters: `staff_member_id`, `awaiting_acknowledgement`. */
  floats(query: TenantListQuery, signal?: AbortSignal): Promise<Page<CashCustodyEntryDto>> {
    return tenantPage(`${base}/floats`, floatPage, query, 'cash floats', signal);
  },
  /** POST /tenant/cash/floats/{id}/acknowledgement (acknowledgeCashFloat). */
  acknowledgeFloat(
    entryId: string,
    body: CashAcknowledgementIn,
    idempotencyKey: string,
  ): Promise<CashCustodyEntryDto> {
    return tenantSend(
      'post',
      `${base}/floats/${seg(entryId)}/acknowledgement`,
      body,
      custodyEntrySchema,
      'cash float',
      idempotencyKey,
    );
  },

  /** POST /tenant/cash/handovers/{id}/decision (decideCashHandover) with the amount actually received. */
  decideRemittance(
    handoverId: string,
    body: RemittanceDecisionIn,
    idempotencyKey: string,
  ): Promise<CashHandoverDto> {
    return tenantSend(
      'post',
      `${base}/handovers/${seg(handoverId)}/decision`,
      body,
      handoverSchema,
      'remittance',
      idempotencyKey,
    );
  },

  /** GET /tenant/cash/variances (listCashVariances). Filters: `status`, `staff_member_id`, `source_type`. */
  variances(query: TenantListQuery, signal?: AbortSignal): Promise<Page<CashVarianceDto>> {
    return tenantPage(`${base}/variances`, variancePage, query, 'cash variances', signal);
  },
  /** GET /tenant/cash/variances/{id} (getCashVariance). */
  variance(varianceId: string, signal?: AbortSignal): Promise<CashVarianceDto> {
    return tenantGet(`${base}/variances/${seg(varianceId)}`, varianceSchema, 'variance', signal);
  },
  /** POST /tenant/cash/variances/{id}/resolution (resolveCashVariance). */
  resolveVariance(
    varianceId: string,
    body: VarianceResolutionIn,
    idempotencyKey: string,
  ): Promise<CashVarianceDto> {
    return tenantSend(
      'post',
      `${base}/variances/${seg(varianceId)}/resolution`,
      body,
      varianceSchema,
      'variance',
      idempotencyKey,
    );
  },
  /** POST /tenant/cash/variances/{id}/write-off-proposal (proposeCashVarianceWriteOff). */
  proposeWriteOff(
    varianceId: string,
    body: WriteOffProposalIn,
    idempotencyKey: string,
  ): Promise<CashVarianceDto> {
    return tenantSend(
      'post',
      `${base}/variances/${seg(varianceId)}/write-off-proposal`,
      body,
      varianceSchema,
      'variance',
      idempotencyKey,
    );
  },
  /** POST /tenant/cash/variances/{id}/write-off-decision (decideCashVarianceWriteOff); never the proposer. */
  decideWriteOff(
    varianceId: string,
    body: CashDecisionIn,
    idempotencyKey: string,
  ): Promise<CashVarianceDto> {
    return tenantSend(
      'post',
      `${base}/variances/${seg(varianceId)}/write-off-decision`,
      body,
      varianceSchema,
      'variance',
      idempotencyKey,
    );
  },

  /** GET /tenant/cash/retentions (listCashRetentions). Filters: `status`, `staff_member_id`. */
  retentions(query: TenantListQuery, signal?: AbortSignal): Promise<Page<CashRetentionDto>> {
    return tenantPage(`${base}/retentions`, retentionPage, query, 'cash retentions', signal);
  },
  /** POST /tenant/cash/retentions (requestCashRetention). */
  requestRetention(body: CashRetentionIn, idempotencyKey: string): Promise<CashRetentionDto> {
    return tenantSend(
      'post',
      `${base}/retentions`,
      body,
      retentionSchema,
      'retention',
      idempotencyKey,
    );
  },
  /** POST /tenant/cash/retentions/{id}/decision (decideCashRetention); never the requester. */
  decideRetention(
    retentionId: string,
    body: CashDecisionIn,
    idempotencyKey: string,
  ): Promise<CashRetentionDto> {
    return tenantSend(
      'post',
      `${base}/retentions/${seg(retentionId)}/decision`,
      body,
      retentionSchema,
      'retention',
      idempotencyKey,
    );
  },

  /** GET /tenant/cash/adjustments (listCustodyAdjustments). Filters: `status`, `staff_member_id`. */
  adjustments(query: TenantListQuery, signal?: AbortSignal): Promise<Page<CustodyAdjustmentDto>> {
    return tenantPage(`${base}/adjustments`, adjustmentPage, query, 'custody adjustments', signal);
  },
  /** POST /tenant/cash/adjustments (proposeCustodyAdjustment). */
  proposeAdjustment(
    body: CustodyAdjustmentIn,
    idempotencyKey: string,
  ): Promise<CustodyAdjustmentDto> {
    return tenantSend(
      'post',
      `${base}/adjustments`,
      body,
      adjustmentSchema,
      'custody adjustment',
      idempotencyKey,
    );
  },
  /** POST /tenant/cash/adjustments/{id}/decision (decideCustodyAdjustment); never the proposer. */
  decideAdjustment(
    adjustmentId: string,
    body: CashDecisionIn,
    idempotencyKey: string,
  ): Promise<CustodyAdjustmentDto> {
    return tenantSend(
      'post',
      `${base}/adjustments/${seg(adjustmentId)}/decision`,
      body,
      adjustmentSchema,
      'custody adjustment',
      idempotencyKey,
    );
  },

  /** GET /tenant/cash/reasons (listCashReasons). Filters: `kind`, `include_inactive`; `q` = label. */
  reasons(query: TenantListQuery, signal?: AbortSignal): Promise<Page<CashReasonDto>> {
    return tenantPage(`${base}/reasons`, reasonPage, query, 'cash reasons', signal);
  },
  /** GET /tenant/cash/reasons/{id} (getCashReason). */
  reason(reasonId: string, signal?: AbortSignal): Promise<CashReasonDto> {
    return tenantGet(`${base}/reasons/${seg(reasonId)}`, reasonSchema, 'cash reason', signal);
  },
  /** POST /tenant/cash/reasons (createCashReason). */
  createReason(body: CashReasonIn, idempotencyKey: string): Promise<CashReasonDto> {
    return tenantSend('post', `${base}/reasons`, body, reasonSchema, 'cash reason', idempotencyKey);
  },
  /** PATCH /tenant/cash/reasons/{id} (updateCashReason). */
  async updateReason(
    reasonId: string,
    body: CashReasonUpdateIn,
    idempotencyKey: string,
  ): Promise<CashReasonDto> {
    const data = await apiClient.patch<unknown>(`${base}/reasons/${seg(reasonId)}`, body, {
      tenantScoped: true,
      idempotencyKey,
    });
    return parseResponse(reasonSchema, data, 'cash reason');
  },
  /** POST /tenant/cash/reasons/{id}/deactivate (deactivateCashReason). */
  deactivateReason(
    reasonId: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ): Promise<CashReasonDto> {
    return tenantLifecycle(
      `${base}/reasons/${seg(reasonId)}/deactivate`,
      body,
      reasonSchema,
      'cash reason',
      idempotencyKey,
    );
  },
  /** POST /tenant/cash/reasons/{id}/reactivate (reactivateCashReason). */
  reactivateReason(
    reasonId: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ): Promise<CashReasonDto> {
    return tenantLifecycle(
      `${base}/reasons/${seg(reasonId)}/reactivate`,
      body,
      reasonSchema,
      'cash reason',
      idempotencyKey,
    );
  },

  /**
   * The transactions behind a reconciliation figure (listCashReconciliationTransactions, or
   * listMyCashReconciliationTransactions when no custodian is given).
   */
  transactions(
    query: TransactionsQuery,
    signal?: AbortSignal,
  ): Promise<Page<CustodyTransactionDto>> {
    const url =
      query.staffMemberId === undefined
        ? `${base}/custody/me/reconciliation/transactions`
        : `${base}/reconciliation/transactions`;
    return tenantGet(url, transactionPage, 'reconciliation transactions', signal, {
      staff_member_id: query.staffMemberId,
      from: query.from,
      to: query.to,
      currency: query.currency,
      figure: query.figure,
      page: query.page,
      page_size: query.page_size,
    });
  },
};
