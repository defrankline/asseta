/**
 * Petty cash fund DTOs (DEC-033): aliases of ./generated/schema.ts, so contract drift fails
 * `npm run typecheck`.
 */
import type { components } from './generated/schema';

type Schemas = components['schemas'];

export type PettyCashFundDto = Schemas['PettyCashFundDto'];
export type PettyCashFundIn = Schemas['PettyCashFundIn'];
export type PettyCashFundUpdateIn = Schemas['PettyCashFundUpdateIn'];
export type PettyCashBalanceDto = Schemas['PettyCashBalanceDto'];
export type PettyCashStatementDto = Schemas['PettyCashStatementDto'];
export type PettyCashStatementLineDto = Schemas['PettyCashStatementLineDto'];
export type PettyCashTransactionDto = Schemas['PettyCashTransactionDto'];
export type FundFigure = Schemas['FundFigure'];
export type TopUpSuggestionDto = Schemas['TopUpSuggestionDto'];
export type TopUpExpenseDto = Schemas['TopUpExpenseDto'];
export type TopUpRequestIn = Schemas['TopUpRequestIn'];
export type PettyCashFundingIn = Schemas['PettyCashFundingIn'];
export type PettyCashDecisionIn = Schemas['PettyCashDecisionIn'];
export type PettyCashIssueIn = Schemas['PettyCashIssueIn'];
export type PettyCashAcknowledgementIn = Schemas['PettyCashAcknowledgementIn'];
export type PettyCashReturnIn = Schemas['PettyCashReturnIn'];
export type PettyCashReturnConfirmIn = Schemas['PettyCashReturnConfirmIn'];
export type PettyCashMovementDto = Schemas['PettyCashMovementDto'];
export type MovementKind = Schemas['MovementKind'];
export type MovementStatus = Schemas['MovementStatus'];
export type PettyCashCountIn = Schemas['PettyCashCountIn'];
export type PettyCashCountDto = Schemas['PettyCashCountDto'];
export type CountReason = Schemas['CountReason'];
export type PettyCashHolderChangeIn = Schemas['PettyCashHolderChangeIn'];
export type PettyCashHolderChangeDecisionIn = Schemas['PettyCashHolderChangeDecisionIn'];
export type PettyCashHolderChangeDto = Schemas['PettyCashHolderChangeDto'];
export type HolderChangeStatus = Schemas['HolderChangeStatus'];
export type PettyCashAdjustmentIn = Schemas['PettyCashAdjustmentIn'];
export type PettyCashAdjustmentDto = Schemas['PettyCashAdjustmentDto'];
export type PettyCashAdvanceIn = Schemas['PettyCashAdvanceIn'];
export type PettyCashAdvanceClearIn = Schemas['PettyCashAdvanceClearIn'];
export type PettyCashAdvanceDto = Schemas['PettyCashAdvanceDto'];
export type AdvanceStatus = Schemas['AdvanceStatus'];
