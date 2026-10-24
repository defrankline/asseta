import type {
  ApprovalDecisionIn,
  ApprovalRequestDto,
  AttachmentDto,
  ExpenseDto,
  ExpenseIn,
  FuelEventDto,
  FuelEventIn,
  Page,
  PhotoUrlDto,
} from '../types';
import { approvalRequestSchema, expenseSchema, fuelEventSchema } from './expenseSchemas';
import { attachmentSchema, photoUrlSchema } from './meterSchemas';
import {
  seg,
  tenantGet,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

const expensePageSchema = tenantPageSchema(expenseSchema);
const fuelPageSchema = tenantPageSchema(fuelEventSchema);
const approvalPageSchema = tenantPageSchema(approvalRequestSchema);

/** Field expenses under the EXPENSE_CAPTURE policy; receipts are fetched via short-lived URLs. */
export const expenseService = {
  /** GET /tenant/expenses (listExpenses). Filters: `status`, `machine_id`, `job_id`, `custodian_staff_id`, `mine`. */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<ExpenseDto>> {
    return tenantPage('/tenant/expenses', expensePageSchema, query, 'expenses', signal);
  },
  /** GET /tenant/expenses/{id} (getExpense). */
  get(expenseId: string, signal?: AbortSignal): Promise<ExpenseDto> {
    return tenantGet(`/tenant/expenses/${seg(expenseId)}`, expenseSchema, 'expense', signal);
  },
  /** POST /tenant/expenses (submitExpense): auto-approved within the policy limit, else PENDING_APPROVAL. */
  submit(body: ExpenseIn, idempotencyKey: string): Promise<ExpenseDto> {
    return tenantSend('post', '/tenant/expenses', body, expenseSchema, 'expense', idempotencyKey);
  },
  /** POST /tenant/expense-receipts (uploadExpenseReceipt), multipart `file`. */
  uploadReceipt(file: File, idempotencyKey: string): Promise<AttachmentDto> {
    const form = new FormData();
    form.append('file', file);
    return tenantSend(
      'post',
      '/tenant/expense-receipts',
      form,
      attachmentSchema,
      'receipt',
      idempotencyKey,
    );
  },
  /** GET /tenant/expenses/{id}/receipts/{attachmentId}/url (getExpenseReceiptUrl): signed, short-lived. */
  receiptUrl(expenseId: string, attachmentId: string, signal?: AbortSignal): Promise<PhotoUrlDto> {
    return tenantGet(
      `/tenant/expenses/${seg(expenseId)}/receipts/${seg(attachmentId)}/url`,
      photoUrlSchema,
      'receipt URL',
      signal,
    );
  },
};

/** Fuel purchase / issue / usage log with cost attribution. */
export const fuelService = {
  /** GET /tenant/fuel-events (listFuelEvents). Filters: `event_type`, `machine_id`, `job_id`, `mine`. */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<FuelEventDto>> {
    return tenantPage('/tenant/fuel-events', fuelPageSchema, query, 'fuel events', signal);
  },
  /** POST /tenant/fuel-events (recordFuelEvent). */
  record(body: FuelEventIn, idempotencyKey: string): Promise<FuelEventDto> {
    return tenantSend(
      'post',
      '/tenant/fuel-events',
      body,
      fuelEventSchema,
      'fuel event',
      idempotencyKey,
    );
  },
};

/** Approval requests raised by expenses above the EXPENSE_CAPTURE auto-approval limit. */
export const approvalService = {
  /** GET /tenant/approvals (listApprovalRequests). Filter: `status`. */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<ApprovalRequestDto>> {
    return tenantPage('/tenant/approvals', approvalPageSchema, query, 'approvals', signal);
  },
  /** POST /tenant/approvals/{id}/decision (decideApprovalRequest); never by the requester. */
  decide(approvalId: string, body: ApprovalDecisionIn, idempotencyKey: string) {
    return tenantSend(
      'post',
      `/tenant/approvals/${seg(approvalId)}/decision`,
      body,
      approvalRequestSchema,
      'approval',
      idempotencyKey,
    );
  },
};
