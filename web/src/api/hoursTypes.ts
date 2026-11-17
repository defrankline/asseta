/**
 * Customer hours DTOs (accountability design A): aliases of ./generated/schema.ts so contract drift
 * fails `npm run typecheck`.
 */
import type { components } from './generated/schema';

type Schemas = components['schemas'];

export type HoursPurchaseDto = Schemas['HoursPurchaseDto'];
export type HoursPurchaseIn = Schemas['HoursPurchaseIn'];
export type HoursQuoteDto = Schemas['HoursQuoteDto'];
/** A payment line method of an order: CREDIT is paid later on the credit invoice the sale creates. */
export type SalePaymentMethod = Schemas['SalePaymentMethod'];
export type CreditInvoiceSummaryDto = Schemas['CreditInvoiceSummaryDto'];
export type CreditInvoiceDto = Schemas['CreditInvoiceDto'];
export type CreditInvoiceStatus = CreditInvoiceDto['status'];
export type CreditInvoicePaymentDto = Schemas['CreditInvoicePaymentDto'];
export type CreditInvoicePaymentIn = Schemas['CreditInvoicePaymentIn'];
export type CustomerHoursSummaryDto = Schemas['CustomerHoursSummaryDto'];
export type HoursPurchaseStatus = HoursPurchaseDto['status'];
export type PurchasePaymentIn = Schemas['PurchasePaymentIn'];
export type PurchaseAllocationDto = Schemas['PurchaseAllocationDto'];
export type PurchaseAllocationIn = Schemas['PurchaseAllocationIn'];
export type PurchaseTotalsDto = Schemas['PurchaseTotalsDto'];
export type MachineHoursDto = Schemas['MachineHoursDto'];
export type CreditActivationIn = Schemas['CreditActivationIn'];
/** Rejecting the credit part of an order ("Reject credit"): its invoice is cancelled, its hours never activate. */
export type CreditRejectionIn = Schemas['CreditRejectionIn'];
export type CreditRejectionDto = Schemas['CreditRejectionDto'];
export type CreditPartStatus = NonNullable<HoursPurchaseDto['credit_status']>;
export type HoursBalanceDto = Schemas['HoursBalanceDto'];
export type LedgerEntryDto = Schemas['LedgerEntryDto'];
export type LedgerEntryType = Schemas['LedgerEntryType'];
export type ActivationSource = Schemas['ActivationSource'];
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

// DEC-031 P2 / P3: low-balance warnings and the customer hours statement.
export type LowBalanceAlertDto = Schemas['LowBalanceAlertDto'];
export type LowBalanceSmsStatus = LowBalanceAlertDto['customer_sms_status'];
export type HoursStatementDto = Schemas['HoursStatementDto'];
export type HoursStatementTotalsDto = Schemas['HoursStatementTotalsDto'];
export type HoursStatementPurchaseDto = Schemas['HoursStatementPurchaseDto'];
export type HoursStatementUsageDto = Schemas['HoursStatementUsageDto'];
export type HoursStatementLineDto = Schemas['HoursStatementLineDto'];
