/** Adjustments ledger and adjustment request DTOs (DEC-032 Phase 2): aliases of ./generated/schema.ts. */
import type { components } from './generated/schema';

type Schemas = components['schemas'];

export type AdjustmentType = Schemas['AdjustmentType'];
export type AdjustmentUnit = Schemas['AdjustmentUnit'];
export type AdjustmentEntryStatus = Schemas['AdjustmentEntryStatus'];
export type AdjustmentEntryDto = Schemas['AdjustmentEntryDto'];
export type AdjustmentRequestType = Schemas['AdjustmentRequestType'];
export type AdjustmentRequestStatus = Schemas['AdjustmentRequestStatus'];
export type AdjustmentRequestDto = Schemas['AdjustmentRequestDto'];
export type AdjustmentRequestIn = Schemas['AdjustmentRequestIn'];
export type AdjustmentDecisionIn = Schemas['AdjustmentDecisionIn'];
export type AdjustmentWithdrawIn = Schemas['AdjustmentWithdrawIn'];
export type RefundSettlement = Schemas['RefundSettlement'];
export type PayoutIn = Schemas['PayoutIn'];
