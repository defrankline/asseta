import type { AttachmentDto, LifecycleChangeIn, Page } from '../types';
import type {
  FundFigure,
  PettyCashAcknowledgementIn,
  PettyCashAdjustmentDto,
  PettyCashAdjustmentIn,
  PettyCashAdvanceClearIn,
  PettyCashAdvanceDto,
  PettyCashAdvanceIn,
  PettyCashBalanceDto,
  PettyCashCountDto,
  PettyCashCountIn,
  PettyCashDecisionIn,
  PettyCashFundDto,
  PettyCashFundIn,
  PettyCashFundingIn,
  PettyCashFundUpdateIn,
  PettyCashHolderChangeDecisionIn,
  PettyCashHolderChangeDto,
  PettyCashHolderChangeIn,
  PettyCashIssueIn,
  PettyCashMovementDto,
  PettyCashReturnConfirmIn,
  PettyCashReturnIn,
  PettyCashStatementDto,
  PettyCashTransactionDto,
  TopUpExpenseDto,
  TopUpRequestIn,
  TopUpSuggestionDto,
} from '../pettyCashTypes';
import { attachmentSchema } from './meterSchemas';
import {
  adjustmentSchema,
  advanceSchema,
  balanceSchema,
  countSchema,
  fundSchema,
  holderChangeSchema,
  movementSchema,
  statementSchema,
  suggestionSchema,
  topUpExpenseSchema,
  transactionSchema,
} from './pettyCashSchemas';
import {
  seg,
  tenantGet,
  tenantLifecycle,
  tenantList,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

const base = '/tenant/petty-cash';
const fundPage = tenantPageSchema(fundSchema);
const movementPage = tenantPageSchema(movementSchema);
const countPage = tenantPageSchema(countSchema);
const holderChangePage = tenantPageSchema(holderChangeSchema);
const adjustmentPage = tenantPageSchema(adjustmentSchema);
const advancePage = tenantPageSchema(advanceSchema);
const fund = (fundId: string) => `${base}/funds/${seg(fundId)}`;
const movement = (movementId: string) => `${base}/movements/${seg(movementId)}`;

/** A tenant-local period (`from` / `to`, YYYY-MM-DD); omitted ends default on the server. */
export interface PettyCashPeriod {
  from?: string | undefined;
  to?: string | undefined;
}

/**
 * Petty cash funds (DEC-033) under /tenant/petty-cash: funds and their ledgers, fundings and top-ups,
 * returns, counts, holder changes, adjustments, advances and evidence. Every call needs the tenant's
 * PETTY_CASH capability; field users only reach the funds they hold.
 */
export const pettyCashService = {
  // --- funds ------------------------------------------------------------------------------------
  /** GET /funds (listPettyCashFunds). Filters: `include_inactive`, `holder_staff_id`, `mine`, `with_balance`. */
  funds(query: TenantListQuery, signal?: AbortSignal): Promise<Page<PettyCashFundDto>> {
    return tenantPage(`${base}/funds`, fundPage, query, 'petty cash funds', signal);
  },
  /** GET /funds/mine (listMyPettyCashFunds): the active funds the caller holds, with balances. */
  myFunds(signal?: AbortSignal): Promise<PettyCashFundDto[]> {
    return tenantList(`${base}/funds/mine`, fundSchema, 'your petty cash funds', signal);
  },
  /** GET /funds/{id} (getPettyCashFund), with its balance. */
  fund(fundId: string, signal?: AbortSignal): Promise<PettyCashFundDto> {
    return tenantGet(fund(fundId), fundSchema, 'petty cash fund', signal);
  },
  /** POST /funds (createPettyCashFund). */
  create(body: PettyCashFundIn, idempotencyKey: string): Promise<PettyCashFundDto> {
    return tenantSend('post', `${base}/funds`, body, fundSchema, 'petty cash fund', idempotencyKey);
  },
  /** PUT /funds/{id} (updatePettyCashFund): code, name, site, limit, low-balance level, note. */
  update(
    fundId: string,
    body: PettyCashFundUpdateIn,
    idempotencyKey: string,
  ): Promise<PettyCashFundDto> {
    return tenantSend('put', fund(fundId), body, fundSchema, 'petty cash fund', idempotencyKey);
  },
  /** POST /funds/{id}/deactivate: only at zero balance with nothing pending. */
  deactivate(
    fundId: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ): Promise<PettyCashFundDto> {
    return tenantLifecycle(
      `${fund(fundId)}/deactivate`,
      body,
      fundSchema,
      'petty cash fund',
      idempotencyKey,
    );
  },
  /** POST /funds/{id}/reactivate. */
  reactivate(
    fundId: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ): Promise<PettyCashFundDto> {
    return tenantLifecycle(
      `${fund(fundId)}/reactivate`,
      body,
      fundSchema,
      'petty cash fund',
      idempotencyKey,
    );
  },
  /** GET /funds/{id}/balance (getPettyCashFundBalance). */
  balance(fundId: string, signal?: AbortSignal): Promise<PettyCashBalanceDto> {
    return tenantGet(`${fund(fundId)}/balance`, balanceSchema, 'fund balance', signal);
  },
  /** GET /funds/{id}/transactions: the records behind each ledger figure, latest first. */
  transactions(
    fundId: string,
    period: PettyCashPeriod & { figure?: FundFigure | undefined },
    signal?: AbortSignal,
  ): Promise<PettyCashTransactionDto[]> {
    return tenantList(`${fund(fundId)}/transactions`, transactionSchema, 'fund records', signal, {
      from: period.from,
      to: period.to,
      figure: period.figure,
    });
  },
  /** GET /funds/{id}/statement: opening balance, every movement with the running balance, closing. */
  statement(
    fundId: string,
    period: PettyCashPeriod,
    signal?: AbortSignal,
  ): Promise<PettyCashStatementDto> {
    return tenantGet(`${fund(fundId)}/statement`, statementSchema, 'fund statement', signal, {
      from: period.from,
      to: period.to,
    });
  },
  /** GET /funds/{id}/top-up-suggestion: approved spending since the last top-up, capped at the limit. */
  topUpSuggestion(fundId: string, signal?: AbortSignal): Promise<TopUpSuggestionDto> {
    return tenantGet(`${fund(fundId)}/top-up-suggestion`, suggestionSchema, 'top-up', signal);
  },
  /** POST /funds/{id}/top-up-requests: the holder asks; someone else approves and issues. */
  requestTopUp(
    fundId: string,
    body: TopUpRequestIn,
    idempotencyKey: string,
  ): Promise<PettyCashMovementDto> {
    return tenantSend(
      'post',
      `${fund(fundId)}/top-up-requests`,
      body,
      movementSchema,
      'top-up request',
      idempotencyKey,
    );
  },

  // --- movements: fundings, top-ups, returns ------------------------------------------------------
  /** POST /fundings (proposePettyCashFunding): FUNDING or TOP_UP; above the cap needs a reason. */
  proposeFunding(body: PettyCashFundingIn, idempotencyKey: string): Promise<PettyCashMovementDto> {
    return tenantSend('post', `${base}/fundings`, body, movementSchema, 'funding', idempotencyKey);
  },
  /** GET /movements. Filters: `fund_id`, `kind`, `status`, `date_from`, `date_to`; `q` = PC- number. */
  movements(query: TenantListQuery, signal?: AbortSignal): Promise<Page<PettyCashMovementDto>> {
    return tenantPage(`${base}/movements`, movementPage, query, 'petty cash movements', signal);
  },
  /** GET /movements/{id}. */
  movement(movementId: string, signal?: AbortSignal): Promise<PettyCashMovementDto> {
    return tenantGet(movement(movementId), movementSchema, 'petty cash movement', signal);
  },
  /** GET /movements/{id}/expenses: the approved spending a top-up proposal was based on. */
  movementExpenses(movementId: string, signal?: AbortSignal): Promise<TopUpExpenseDto[]> {
    return tenantList(
      `${movement(movementId)}/expenses`,
      topUpExpenseSchema,
      'top-up expenses',
      signal,
    );
  },
  /** POST /movements/{id}/decision: never the proposer, never the fund's holder. */
  decideMovement(
    movementId: string,
    body: PettyCashDecisionIn,
    idempotencyKey: string,
  ): Promise<PettyCashMovementDto> {
    return tenantSend(
      'post',
      `${movement(movementId)}/decision`,
      body,
      movementSchema,
      'petty cash decision',
      idempotencyKey,
    );
  },
  /** POST /movements/{id}/issue: hand the approved money over (never by the holder). */
  issue(
    movementId: string,
    body: PettyCashIssueIn,
    idempotencyKey: string,
  ): Promise<PettyCashMovementDto> {
    return tenantSend(
      'post',
      `${movement(movementId)}/issue`,
      body,
      movementSchema,
      'petty cash hand-over',
      idempotencyKey,
    );
  },
  /** POST /movements/{id}/acknowledgement: the holder confirms the amount received or disputes it. */
  acknowledge(
    movementId: string,
    body: PettyCashAcknowledgementIn,
    idempotencyKey: string,
  ): Promise<PettyCashMovementDto> {
    return tenantSend(
      'post',
      `${movement(movementId)}/acknowledgement`,
      body,
      movementSchema,
      'acknowledgement',
      idempotencyKey,
    );
  },
  /** POST /returns (claimPettyCashReturn): the holder hands money back (counts once confirmed). */
  claimReturn(body: PettyCashReturnIn, idempotencyKey: string): Promise<PettyCashMovementDto> {
    return tenantSend('post', `${base}/returns`, body, movementSchema, 'return', idempotencyKey);
  },
  /** POST /movements/{id}/confirmation: the office confirms the amount it counted. */
  confirmReturn(
    movementId: string,
    body: PettyCashReturnConfirmIn,
    idempotencyKey: string,
  ): Promise<PettyCashMovementDto> {
    return tenantSend(
      'post',
      `${movement(movementId)}/confirmation`,
      body,
      movementSchema,
      'return confirmation',
      idempotencyKey,
    );
  },

  // --- counts -------------------------------------------------------------------------------------
  /** POST /counts (recordPettyCashCount): a difference opens a variance. */
  recordCount(body: PettyCashCountIn, idempotencyKey: string): Promise<PettyCashCountDto> {
    return tenantSend('post', `${base}/counts`, body, countSchema, 'count', idempotencyKey);
  },
  /** GET /counts. Filters: `fund_id`; `q` = number. */
  counts(query: TenantListQuery, signal?: AbortSignal): Promise<Page<PettyCashCountDto>> {
    return tenantPage(`${base}/counts`, countPage, query, 'petty cash counts', signal);
  },
  /** GET /counts/{id}. */
  count(countId: string, signal?: AbortSignal): Promise<PettyCashCountDto> {
    return tenantGet(`${base}/counts/${seg(countId)}`, countSchema, 'petty cash count', signal);
  },

  // --- holder changes -----------------------------------------------------------------------------
  /** POST /funds/{id}/holder-changes: count at the change; the new holder then accepts. */
  startHolderChange(
    fundId: string,
    body: PettyCashHolderChangeIn,
    idempotencyKey: string,
  ): Promise<PettyCashHolderChangeDto> {
    return tenantSend(
      'post',
      `${fund(fundId)}/holder-changes`,
      body,
      holderChangeSchema,
      'holder change',
      idempotencyKey,
    );
  },
  /** GET /holder-changes. Filters: `fund_id`, `status`. */
  holderChanges(
    query: TenantListQuery,
    signal?: AbortSignal,
  ): Promise<Page<PettyCashHolderChangeDto>> {
    return tenantPage(`${base}/holder-changes`, holderChangePage, query, 'holder changes', signal);
  },
  /** GET /holder-changes/{id}. */
  holderChange(changeId: string, signal?: AbortSignal): Promise<PettyCashHolderChangeDto> {
    return tenantGet(
      `${base}/holder-changes/${seg(changeId)}`,
      holderChangeSchema,
      'holder change',
      signal,
    );
  },
  /** POST /holder-changes/{id}/acknowledgement: the new holder accepts or declines. */
  answerHolderChange(
    changeId: string,
    body: PettyCashHolderChangeDecisionIn,
    idempotencyKey: string,
  ): Promise<PettyCashHolderChangeDto> {
    return tenantSend(
      'post',
      `${base}/holder-changes/${seg(changeId)}/acknowledgement`,
      body,
      holderChangeSchema,
      'holder change',
      idempotencyKey,
    );
  },
  /** POST /holder-changes/{id}/cancel. */
  cancelHolderChange(
    changeId: string,
    note: string | null,
    idempotencyKey: string,
  ): Promise<PettyCashHolderChangeDto> {
    return tenantSend(
      'post',
      `${base}/holder-changes/${seg(changeId)}/cancel`,
      { note },
      holderChangeSchema,
      'holder change',
      idempotencyKey,
    );
  },

  // --- adjustments --------------------------------------------------------------------------------
  /** POST /adjustments: a signed correction with a reason; decided by someone else. */
  proposeAdjustment(
    body: PettyCashAdjustmentIn,
    idempotencyKey: string,
  ): Promise<PettyCashAdjustmentDto> {
    return tenantSend(
      'post',
      `${base}/adjustments`,
      body,
      adjustmentSchema,
      'fund adjustment',
      idempotencyKey,
    );
  },
  /** GET /adjustments. Filters: `fund_id`, `status`; `q` = number / reason. */
  adjustments(query: TenantListQuery, signal?: AbortSignal): Promise<Page<PettyCashAdjustmentDto>> {
    return tenantPage(`${base}/adjustments`, adjustmentPage, query, 'fund adjustments', signal);
  },
  /** GET /adjustments/{id}. */
  adjustment(adjustmentId: string, signal?: AbortSignal): Promise<PettyCashAdjustmentDto> {
    return tenantGet(
      `${base}/adjustments/${seg(adjustmentId)}`,
      adjustmentSchema,
      'fund adjustment',
      signal,
    );
  },
  /** POST /adjustments/{id}/decision: never the proposer, never the holder. */
  decideAdjustment(
    adjustmentId: string,
    body: PettyCashDecisionIn,
    idempotencyKey: string,
  ): Promise<PettyCashAdjustmentDto> {
    return tenantSend(
      'post',
      `${base}/adjustments/${seg(adjustmentId)}/decision`,
      body,
      adjustmentSchema,
      'fund adjustment',
      idempotencyKey,
    );
  },

  // --- advances (only while the tenant's PETTY_CASH policy switches them on) ---------------------
  /** POST /advances: cash out of the fund to someone before a purchase. */
  issueAdvance(body: PettyCashAdvanceIn, idempotencyKey: string): Promise<PettyCashAdvanceDto> {
    return tenantSend('post', `${base}/advances`, body, advanceSchema, 'advance', idempotencyKey);
  },
  /** GET /advances. Filters: `fund_id`, `status`, `recipient_staff_id`; `q` = number / purpose. */
  advances(query: TenantListQuery, signal?: AbortSignal): Promise<Page<PettyCashAdvanceDto>> {
    return tenantPage(`${base}/advances`, advancePage, query, 'advances', signal);
  },
  /** GET /advances/{id}. */
  advance(advanceId: string, signal?: AbortSignal): Promise<PettyCashAdvanceDto> {
    return tenantGet(`${base}/advances/${seg(advanceId)}`, advanceSchema, 'advance', signal);
  },
  /** POST /advances/{id}/clearance: the holder takes the change back. */
  clearAdvance(
    advanceId: string,
    body: PettyCashAdvanceClearIn,
    idempotencyKey: string,
  ): Promise<PettyCashAdvanceDto> {
    return tenantSend(
      'post',
      `${base}/advances/${seg(advanceId)}/clearance`,
      body,
      advanceSchema,
      'advance',
      idempotencyKey,
    );
  },

  // --- evidence -----------------------------------------------------------------------------------
  /** POST /evidence (uploadPettyCashEvidence), multipart `file`: a slip, the cash or a count sheet. */
  uploadEvidence(file: File, idempotencyKey: string): Promise<AttachmentDto> {
    const form = new FormData();
    form.append('file', file);
    return tenantSend(
      'post',
      `${base}/evidence`,
      form,
      attachmentSchema,
      'evidence',
      idempotencyKey,
    );
  },
};
