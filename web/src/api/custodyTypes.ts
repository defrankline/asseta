/**
 * Cash custody chain and oversight DTOs (accountability design C/D): aliases of ./generated/schema.ts,
 * so contract drift fails `npm run typecheck`.
 */
import type { components } from './generated/schema';

type Schemas = components['schemas'];

export type RemittanceDecisionIn = Schemas['RemittanceDecisionIn'];
export type CustodianDto = Schemas['CustodianDto'];
export type CashTransferIn = Schemas['CashTransferIn'];
export type CashTransferDto = Schemas['CashTransferDto'];
export type CashTransferStatus = Schemas['CashTransferStatus'];
export type CashAcknowledgementIn = Schemas['CashAcknowledgementIn'];
export type CashAckMethod = Schemas['AcknowledgementMethod'];
export type CashVarianceDto = Schemas['CashVarianceDto'];
export type VarianceSource = Schemas['VarianceSource'];
export type VarianceStatus = Schemas['VarianceStatus'];
export type VarianceOutcome = Schemas['VarianceOutcome'];
export type VarianceResolutionIn = Schemas['VarianceResolutionIn'];
export type WriteOffProposalIn = Schemas['WriteOffProposalIn'];
export type CashDecisionIn = Schemas['DecisionIn'];
export type CashDecisionStatus = Schemas['CashDecisionStatus'];
export type CashRetentionIn = Schemas['CashRetentionIn'];
export type CashRetentionDto = Schemas['CashRetentionDto'];
export type CustodyAdjustmentIn = Schemas['CustodyAdjustmentIn'];
export type CustodyAdjustmentDto = Schemas['CustodyAdjustmentDto'];
export type CustodyAdjustmentKind = Schemas['CustodyAdjustmentKind'];
export type CashReasonKind = Schemas['CashReasonKind'];
export type CashReasonIn = Schemas['CashReasonIn'];
export type CashReasonUpdateIn = Schemas['CashReasonUpdateIn'];
export type CashReasonDto = Schemas['CashReasonDto'];
export type ReconciliationFigure = Schemas['ReconciliationFigure'];
export type CustodyTransactionDto = Schemas['CustodyTransactionDto'];
export type SecurityEventDto = Schemas['SecurityEventDto'];
export type SecurityEventKind = Schemas['SecurityEventKind'];
export type SyncConflictDto = Schemas['SyncConflictDto'];
export type SyncResolutionIn = Schemas['SyncResolutionIn'];
export type SyncResolutionOutcome = Schemas['SyncResolutionOutcome'];
export type AccountabilitySummaryDto = Schemas['AccountabilitySummaryDto'];
export type CountAmountDto = Schemas['CountAmountDto'];
export type CustodianCashDto = Schemas['CustodianCashDto'];
export type RemittanceOverdueDto = Schemas['RemittanceOverdueDto'];
export type OverdueAmountDto = Schemas['OverdueAmountDto'];
// DEC-031 Phase 3: company deposit accounts and stronger remittances.
export type DepositAccountDto = Schemas['DepositAccountDto'];
export type DepositAccountIn = Schemas['DepositAccountIn'];
export type DepositAccountUpdateIn = Schemas['DepositAccountUpdateIn'];
export type DepositAccountType = Schemas['DepositAccountType'];
export type RemittanceMethod = Schemas['RemittanceMethod'];
export type RemittanceEvidenceDto = Schemas['RemittanceEvidenceDto'];
export type OverdueReason = Schemas['OverdueReason'];
