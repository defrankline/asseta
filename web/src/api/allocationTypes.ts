/** Work allocation ledger and daily operational report DTOs (DEC-032 Phase 1): aliases of ./generated/schema.ts. */
import type { components } from './generated/schema';

type Schemas = components['schemas'];

export type AllocationKind = Schemas['AllocationKind'];
export type AllocationSource = Schemas['AllocationSource'];
export type AllocationStatus = Schemas['AllocationStatus'];
export type AllocationLotDto = Schemas['AllocationLotDto'];
export type WorkAllocationDto = Schemas['WorkAllocationDto'];
export type AllocationDayDto = Schemas['AllocationDayDto'];
export type AllocationPartIn = Schemas['AllocationPartIn'];
export type AllocationCorrectionIn = Schemas['AllocationCorrectionIn'];
export type AllocationCorrectionDto = Schemas['AllocationCorrectionDto'];
export type DailyReportStatus = Schemas['DailyReportStatus'];
export type UnbillableLineDto = Schemas['UnbillableLineDto'];
export type UnbillableLineIn = Schemas['UnbillableLineIn'];
export type ReportAllocationDto = Schemas['ReportAllocationDto'];
export type DailyReportDto = Schemas['DailyReportDto'];
export type DailyReportIn = Schemas['DailyReportIn'];
export type DailyReportPrefillDto = Schemas['DailyReportPrefillDto'];
export type DailyReportReviewIn = Schemas['DailyReportReviewIn'];
