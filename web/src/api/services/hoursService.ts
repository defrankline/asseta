import { array, type Schema } from 'yup';
import type {
  CancellationDto,
  CancellationIn,
  CreditActivationIn,
  CreditArrangementDto,
  CreditArrangementIn,
  CreditArrangementUpdateIn,
  CreditExposureDto,
  CustomerRegistrationIn,
  DecisionIn,
  DiscountDto,
  DiscountIn,
  DiscountUpdateIn,
  EvidenceLinkIn,
  HoursBalanceDto,
  HoursPurchaseDto,
  HoursPurchaseIn,
  LedgerEntryDto,
  PaymentEvidenceDto,
  PurchaseAllocationIn,
  ReasonCodeDto,
  ReasonCodeIn,
  ReasonCodeUpdateIn,
  ReasonIn,
  ReasonKind,
  TransferDto,
  TransferIn,
  WalkInCustomerDto,
  WalkInCustomerIn,
  WorkExecutionAllocationDto,
} from '../hoursTypes';
import type { AttachmentDto, CustomerDto, LifecycleChangeIn, Page, PhotoUrlDto } from '../types';
import {
  cancellationSchema,
  creditArrangementSchema,
  creditExposureSchema,
  discountSchema,
  hoursBalanceSchema,
  hoursPurchaseSchema,
  ledgerEntrySchema,
  paymentEvidenceSchema,
  reasonCodeSchema,
  transferSchema,
  walkInCustomerSchema,
  workExecutionAllocationSchema,
} from './hoursSchemas';
import { customerSchema } from './jobSchemas';
import { attachmentSchema, photoUrlSchema } from './meterSchemas';
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

const T = '/tenant';
const purchasePage = tenantPageSchema(hoursPurchaseSchema);
const ledgerPage = tenantPageSchema(ledgerEntrySchema);
const allocationPage = tenantPageSchema(workExecutionAllocationSchema);
const transferPage = tenantPageSchema(transferSchema);
const cancellationPage = tenantPageSchema(cancellationSchema);
const reasonPage = tenantPageSchema(reasonCodeSchema);

/** Customer hours: walk-ins, purchases (payments, credit, cancellation), ledger, balances, allocations. */
export const hoursService = {
  /** POST /tenant/walk-in-customers (createWalkInCustomer). */
  createWalkIn(body: WalkInCustomerIn, idempotencyKey: string): Promise<WalkInCustomerDto> {
    return tenantSend(
      'post',
      `${T}/walk-in-customers`,
      body,
      walkInCustomerSchema,
      'walk-in customer',
      idempotencyKey,
    );
  },
  /** POST /tenant/customers/{id}/registration (registerWalkInCustomer): upgrade a walk-in. */
  registerWalkIn(
    customerId: string,
    body: CustomerRegistrationIn,
    idempotencyKey: string,
  ): Promise<CustomerDto> {
    return tenantSend(
      'post',
      `${T}/customers/${seg(customerId)}/registration`,
      body,
      customerSchema,
      'customer',
      idempotencyKey,
    );
  },
  /** GET /tenant/hours-purchases (listHoursPurchases). Filters: `customer_id`, `machine_id`, `cancelled`. */
  listPurchases(query: TenantListQuery, signal?: AbortSignal): Promise<Page<HoursPurchaseDto>> {
    return tenantPage(`${T}/hours-purchases`, purchasePage, query, 'hours purchases', signal);
  },
  /** GET /tenant/hours-purchases/{id} (getHoursPurchase). */
  getPurchase(purchaseId: string, signal?: AbortSignal): Promise<HoursPurchaseDto> {
    return tenantGet(
      `${T}/hours-purchases/${seg(purchaseId)}`,
      hoursPurchaseSchema,
      'hours purchase',
      signal,
    );
  },
  /** POST /tenant/hours-purchases (recordHoursPurchase): optional walk-in and cash payment. */
  recordPurchase(body: HoursPurchaseIn, idempotencyKey: string): Promise<HoursPurchaseDto> {
    return tenantSend(
      'post',
      `${T}/hours-purchases`,
      body,
      hoursPurchaseSchema,
      'hours purchase',
      idempotencyKey,
    );
  },
  /** POST /tenant/hours-purchases/{id}/allocations (allocatePaymentToHoursPurchase). */
  allocatePayment(
    purchaseId: string,
    body: PurchaseAllocationIn,
    idempotencyKey: string,
  ): Promise<HoursPurchaseDto> {
    return tenantSend(
      'post',
      `${T}/hours-purchases/${seg(purchaseId)}/allocations`,
      body,
      hoursPurchaseSchema,
      'hours purchase',
      idempotencyKey,
    );
  },
  /** POST /tenant/hours-purchases/{id}/credit-activations (activateHoursOnCredit). */
  activateOnCredit(
    purchaseId: string,
    body: CreditActivationIn,
    idempotencyKey: string,
  ): Promise<HoursPurchaseDto> {
    return tenantSend(
      'post',
      `${T}/hours-purchases/${seg(purchaseId)}/credit-activations`,
      body,
      hoursPurchaseSchema,
      'hours purchase',
      idempotencyKey,
    );
  },
  /** POST /tenant/hours-purchases/{id}/cancellation (requestHoursPurchaseCancellation). */
  requestCancellation(
    purchaseId: string,
    body: CancellationIn,
    idempotencyKey: string,
  ): Promise<CancellationDto> {
    return tenantSend(
      'post',
      `${T}/hours-purchases/${seg(purchaseId)}/cancellation`,
      body,
      cancellationSchema,
      'cancellation',
      idempotencyKey,
    );
  },
  /** GET /tenant/hours-ledger (listHoursLedger). Filters: purchase, customer, machine, job, entry type. */
  listLedger(query: TenantListQuery, signal?: AbortSignal): Promise<Page<LedgerEntryDto>> {
    return tenantPage(`${T}/hours-ledger`, ledgerPage, query, 'hours ledger', signal);
  },
  /** GET /tenant/customers/{id}/hours-balances (getCustomerHoursBalances): one row per machine. */
  customerBalances(customerId: string, signal?: AbortSignal): Promise<HoursBalanceDto[]> {
    return tenantList(
      `${T}/customers/${seg(customerId)}/hours-balances`,
      hoursBalanceSchema,
      'hours balances',
      signal,
    );
  },
  /** GET /tenant/machines/{id}/hours-balances (getMachineHoursBalances): one row per customer. */
  machineBalances(machineId: string, signal?: AbortSignal): Promise<HoursBalanceDto[]> {
    return tenantList(
      `${T}/machines/${seg(machineId)}/hours-balances`,
      hoursBalanceSchema,
      'hours balances',
      signal,
    );
  },
  /** GET /tenant/customers/{id}/credit-exposure (getCustomerCreditExposure). */
  creditExposure(
    customerId: string,
    currency: string | undefined,
    signal?: AbortSignal,
  ): Promise<CreditExposureDto> {
    return tenantGet(
      `${T}/customers/${seg(customerId)}/credit-exposure`,
      creditExposureSchema,
      'credit exposure',
      signal,
      { currency },
    );
  },
  /** GET /tenant/work-execution-allocations (listWorkExecutionAllocations). */
  listAllocations(
    query: TenantListQuery,
    signal?: AbortSignal,
  ): Promise<Page<WorkExecutionAllocationDto>> {
    return tenantPage(
      `${T}/work-execution-allocations`,
      allocationPage,
      query,
      'work allocations',
      signal,
    );
  },
  /** GET /tenant/work-execution-allocations/{id} (getWorkExecutionAllocation). */
  getAllocation(allocationId: string, signal?: AbortSignal): Promise<WorkExecutionAllocationDto> {
    return tenantGet(
      `${T}/work-execution-allocations/${seg(allocationId)}`,
      workExecutionAllocationSchema,
      'work allocation',
      signal,
    );
  },
  /** POST /tenant/payment-evidence (uploadPaymentEvidence), multipart `file`. */
  uploadEvidence(file: File, idempotencyKey: string): Promise<AttachmentDto> {
    const form = new FormData();
    form.append('file', file);
    return tenantSend(
      'post',
      `${T}/payment-evidence`,
      form,
      attachmentSchema,
      'attachment',
      idempotencyKey,
    );
  },
  /** GET /tenant/customer-payments/{id}/evidence (listPaymentEvidence). */
  listEvidence(paymentId: string, signal?: AbortSignal): Promise<PaymentEvidenceDto[]> {
    return tenantList(
      `${T}/customer-payments/${seg(paymentId)}/evidence`,
      paymentEvidenceSchema,
      'payment evidence',
      signal,
    );
  },
  /** POST /tenant/customer-payments/{id}/evidence (attachPaymentEvidence). */
  attachEvidence(
    paymentId: string,
    body: EvidenceLinkIn,
    idempotencyKey: string,
  ): Promise<PaymentEvidenceDto[]> {
    return tenantSend(
      'post',
      `${T}/customer-payments/${seg(paymentId)}/evidence`,
      body,
      array(paymentEvidenceSchema).required(),
      'payment evidence',
      idempotencyKey,
    );
  },
  /** GET /tenant/customer-payments/{id}/evidence/{attachment}/url (getPaymentEvidenceUrl). */
  evidenceUrl(paymentId: string, attachmentId: string, signal?: AbortSignal): Promise<PhotoUrlDto> {
    return tenantGet(
      `${T}/customer-payments/${seg(paymentId)}/evidence/${seg(attachmentId)}/url`,
      photoUrlSchema,
      'evidence URL',
      signal,
    );
  },
};

/** Hours transfers between machines and purchase cancellations (requested, decided by someone else). */
export const hoursRequestService = {
  /** GET /tenant/hours-transfers (listHoursTransfers). Filters: `status`, `purchase_id`. */
  listTransfers(query: TenantListQuery, signal?: AbortSignal): Promise<Page<TransferDto>> {
    return tenantPage(`${T}/hours-transfers`, transferPage, query, 'hours transfers', signal);
  },
  /** POST /tenant/hours-transfers (requestHoursTransfer). */
  requestTransfer(body: TransferIn, idempotencyKey: string): Promise<TransferDto> {
    return tenantSend(
      'post',
      `${T}/hours-transfers`,
      body,
      transferSchema,
      'hours transfer',
      idempotencyKey,
    );
  },
  /** POST /tenant/hours-transfers/{id}/decision (decideHoursTransfer). */
  decideTransfer(id: string, body: DecisionIn, idempotencyKey: string): Promise<TransferDto> {
    return tenantSend(
      'post',
      `${T}/hours-transfers/${seg(id)}/decision`,
      body,
      transferSchema,
      'hours transfer',
      idempotencyKey,
    );
  },
  /** POST /tenant/hours-transfers/{id}/withdraw (withdrawHoursTransfer): requester only. */
  withdrawTransfer(id: string, body: ReasonIn, idempotencyKey: string): Promise<TransferDto> {
    return tenantSend(
      'post',
      `${T}/hours-transfers/${seg(id)}/withdraw`,
      body,
      transferSchema,
      'hours transfer',
      idempotencyKey,
    );
  },
  /** GET /tenant/hours-cancellations (listHoursCancellations). Filters: `status`, `purchase_id`. */
  listCancellations(query: TenantListQuery, signal?: AbortSignal): Promise<Page<CancellationDto>> {
    return tenantPage(
      `${T}/hours-cancellations`,
      cancellationPage,
      query,
      'hours cancellations',
      signal,
    );
  },
  /** POST /tenant/hours-cancellations/{id}/decision (decideHoursCancellation). */
  decideCancellation(
    id: string,
    body: DecisionIn,
    idempotencyKey: string,
  ): Promise<CancellationDto> {
    return tenantSend(
      'post',
      `${T}/hours-cancellations/${seg(id)}/decision`,
      body,
      cancellationSchema,
      'cancellation',
      idempotencyKey,
    );
  },
  /** POST /tenant/hours-cancellations/{id}/withdraw (withdrawHoursCancellation): requester only. */
  withdrawCancellation(
    id: string,
    body: ReasonIn,
    idempotencyKey: string,
  ): Promise<CancellationDto> {
    return tenantSend(
      'post',
      `${T}/hours-cancellations/${seg(id)}/withdraw`,
      body,
      cancellationSchema,
      'cancellation',
      idempotencyKey,
    );
  },
};

/** Proposal endpoints shared by customer discounts and credit arrangements. */
export interface ProposalService<D, I, U> {
  list: (query: TenantListQuery, signal?: AbortSignal) => Promise<Page<D>>;
  get: (id: string, signal?: AbortSignal) => Promise<D>;
  propose: (body: I, idempotencyKey: string) => Promise<D>;
  update: (id: string, body: U, idempotencyKey: string) => Promise<D>;
  decide: (id: string, body: DecisionIn, idempotencyKey: string) => Promise<D>;
  withdraw: (id: string, body: ReasonIn, idempotencyKey: string) => Promise<D>;
  revoke: (id: string, body: ReasonIn, idempotencyKey: string) => Promise<D>;
}

const proposalCalls = <D>(path: string, schema: Schema<D>) => {
  const page = tenantPageSchema(schema);
  const one = (id: string) => `${T}/${path}/${seg(id)}`;
  return {
    list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<D>> {
      return tenantPage(`${T}/${path}`, page, query, path, signal);
    },
    get(id: string, signal?: AbortSignal): Promise<D> {
      return tenantGet(one(id), schema, path, signal);
    },
    propose(body: unknown, idempotencyKey: string): Promise<D> {
      return tenantSend('post', `${T}/${path}`, body, schema, path, idempotencyKey);
    },
    update(id: string, body: unknown, idempotencyKey: string): Promise<D> {
      return tenantSend('put', one(id), body, schema, path, idempotencyKey);
    },
    decide(id: string, body: DecisionIn, idempotencyKey: string): Promise<D> {
      return tenantSend('post', `${one(id)}/decision`, body, schema, path, idempotencyKey);
    },
    withdraw(id: string, body: ReasonIn, idempotencyKey: string): Promise<D> {
      return tenantSend('post', `${one(id)}/withdraw`, body, schema, path, idempotencyKey);
    },
    revoke(id: string, body: ReasonIn, idempotencyKey: string): Promise<D> {
      return tenantSend('post', `${one(id)}/revoke`, body, schema, path, idempotencyKey);
    },
  };
};

/** Customer discounts (listCustomerDiscounts, propose/update/decision/withdraw/revoke). */
export const discountService: ProposalService<DiscountDto, DiscountIn, DiscountUpdateIn> =
  proposalCalls('customer-discounts', discountSchema);

/** Credit arrangements (listCreditArrangements, propose/update/decision/withdraw/revoke). */
export const creditArrangementService: ProposalService<
  CreditArrangementDto,
  CreditArrangementIn,
  CreditArrangementUpdateIn
> = proposalCalls('credit-arrangements', creditArrangementSchema);

/** The tenant's hours reason lists (discount / credit / transfer / cancellation). */
export const hoursReasonService = {
  /** GET /tenant/hours-reason-codes (listHoursReasonCodes). Filters: `kind`, `include_inactive`. */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<ReasonCodeDto>> {
    return tenantPage(`${T}/hours-reason-codes`, reasonPage, query, 'reason codes', signal);
  },
  /** Active reasons of one kind matching `q` (picker lookup). */
  async search(kind: ReasonKind, q: string, signal: AbortSignal): Promise<ReasonCodeDto[]> {
    return (await this.list({ page: 1, page_size: 20, q, filters: { kind } }, signal)).items;
  },
  /** GET /tenant/hours-reason-codes/{id} (getHoursReasonCode). */
  get(id: string, signal?: AbortSignal): Promise<ReasonCodeDto> {
    return tenantGet(`${T}/hours-reason-codes/${seg(id)}`, reasonCodeSchema, 'reason', signal);
  },
  /** POST /tenant/hours-reason-codes (createHoursReasonCode). */
  create(body: ReasonCodeIn, idempotencyKey: string): Promise<ReasonCodeDto> {
    return tenantSend(
      'post',
      `${T}/hours-reason-codes`,
      body,
      reasonCodeSchema,
      'reason',
      idempotencyKey,
    );
  },
  /** PUT /tenant/hours-reason-codes/{id} (updateHoursReasonCode). */
  update(id: string, body: ReasonCodeUpdateIn, idempotencyKey: string): Promise<ReasonCodeDto> {
    return tenantSend(
      'put',
      `${T}/hours-reason-codes/${seg(id)}`,
      body,
      reasonCodeSchema,
      'reason',
      idempotencyKey,
    );
  },
  /** POST /tenant/hours-reason-codes/{id}/deactivate (deactivateHoursReasonCode). */
  deactivate(id: string, body: LifecycleChangeIn, idempotencyKey: string): Promise<ReasonCodeDto> {
    return tenantLifecycle(
      `${T}/hours-reason-codes/${seg(id)}/deactivate`,
      body,
      reasonCodeSchema,
      'reason',
      idempotencyKey,
    );
  },
  /** POST /tenant/hours-reason-codes/{id}/reactivate (reactivateHoursReasonCode). */
  reactivate(id: string, body: LifecycleChangeIn, idempotencyKey: string): Promise<ReasonCodeDto> {
    return tenantLifecycle(
      `${T}/hours-reason-codes/${seg(id)}/reactivate`,
      body,
      reasonCodeSchema,
      'reason',
      idempotencyKey,
    );
  },
};
