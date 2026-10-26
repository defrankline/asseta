/**
 * Customer hours DTOs (accountability design A): aliases of ./generated/schema.ts so contract drift
 * fails `npm run typecheck`.
 */
import type { components } from './generated/schema';

type Schemas = components['schemas'];

export type HoursPurchaseDto = Schemas['HoursPurchaseDto'];
export type HoursPurchaseIn = Schemas['HoursPurchaseIn'];
export type HoursPurchaseStatus = HoursPurchaseDto['status'];
export type PurchasePaymentIn = Schemas['PurchasePaymentIn'];
export type PurchaseAllocationDto = Schemas['PurchaseAllocationDto'];
export type PurchaseAllocationIn = Schemas['PurchaseAllocationIn'];
export type PurchaseTotalsDto = Schemas['PurchaseTotalsDto'];
export type MachineHoursDto = Schemas['MachineHoursDto'];
export type CreditActivationIn = Schemas['CreditActivationIn'];
export type HoursBalanceDto = Schemas['HoursBalanceDto'];
export type LedgerEntryDto = Schemas['LedgerEntryDto'];
export type LedgerEntryType = Schemas['LedgerEntryType'];
export type ActivationSource = Schemas['ActivationSource'];
export type WorkExecutionAllocationDto = Schemas['WorkExecutionAllocationDto'];
export type AllocationLineDto = Schemas['AllocationLineDto'];
export type TransferDto = Schemas['TransferDto'];
export type TransferIn = Schemas['TransferIn'];
export type CancellationDto = Schemas['CancellationDto'];
export type CancellationIn = Schemas['CancellationIn'];
export type RequestStatus = Schemas['RequestStatus'];
export type ProposalStatus = Schemas['ProposalStatus'];
export type DiscountDto = Schemas['DiscountDto'];
export type DiscountIn = Schemas['DiscountIn'];
export type DiscountUpdateIn = Schemas['DiscountUpdateIn'];
export type CreditArrangementDto = Schemas['CreditArrangementDto'];
export type CreditArrangementIn = Schemas['CreditArrangementIn'];
export type CreditArrangementUpdateIn = Schemas['CreditArrangementUpdateIn'];
export type CreditExposureDto = Schemas['CreditExposureDto'];
export type DecisionIn = Schemas['DecisionIn'];
export type ReasonIn = Schemas['ReasonIn'];
export type ReasonCodeDto = Schemas['ReasonCodeDto'];
export type ReasonCodeIn = Schemas['ReasonCodeIn'];
export type ReasonCodeUpdateIn = Schemas['ReasonCodeUpdateIn'];
export type ReasonKind = Schemas['ReasonKind'];
export type WalkInCustomerIn = Schemas['WalkInCustomerIn'];
export type WalkInCustomerDto = Schemas['WalkInCustomerDto'];
export type CustomerRegistrationIn = Schemas['CustomerRegistrationIn'];
export type CustomerKind = Schemas['CustomerKind'];
export type PaymentEvidenceDto = Schemas['PaymentEvidenceDto'];
export type EvidenceLinkIn = Schemas['EvidenceLinkIn'];
export type BillingMode = Schemas['BillingMode'];

// DEC-031 P2 / P3: low-balance warnings and the customer hours statement.
export type LowBalanceAlertDto = Schemas['LowBalanceAlertDto'];
export type LowBalanceSmsStatus = LowBalanceAlertDto['customer_sms_status'];
export type HoursStatementDto = Schemas['HoursStatementDto'];
export type HoursStatementTotalsDto = Schemas['HoursStatementTotalsDto'];
export type HoursStatementPurchaseDto = Schemas['HoursStatementPurchaseDto'];
export type HoursStatementUsageDto = Schemas['HoursStatementUsageDto'];
export type HoursStatementLineDto = Schemas['HoursStatementLineDto'];
