/** Revenue reconciliation (DEC-031 R1–R3) contract types: daily machine sheet, differences, non-revenue time. */
import type { components } from './generated/schema';

type Schemas = components['schemas'];

export type SheetFlag = Schemas['SheetFlag'];
export type SheetMoneyDto = Schemas['SheetMoneyDto'];
export type SheetJobDto = Schemas['SheetJobDto'];
export type SheetReadingDto = Schemas['SheetReadingDto'];
export type SheetSegmentDto = Schemas['SheetSegmentDto'];
export type SheetMoneySourceDto = Schemas['SheetMoneySourceDto'];
export type SheetFlagRefDto = Schemas['SheetFlagRefDto'];
export type SheetFuelDto = Schemas['SheetFuelDto'];
export type DailyMachineSheetRowDto = Schemas['DailyMachineSheetRowDto'];
export type DailyMachineSheetDetailDto = Schemas['DailyMachineSheetDetailDto'];
export type RevenueReasonDto = Schemas['RevenueReasonDto'];
export type RevenueReasonIn = Schemas['RevenueReasonIn'];
export type RevenueReasonUpdateIn = Schemas['RevenueReasonUpdateIn'];
export type RevenueDifferenceStatus = Schemas['RevenueDifferenceStatus'];
export type RevenueDifferenceDto = Schemas['RevenueDifferenceDto'];
export type RevenueAdjustmentDto = Schemas['RevenueAdjustmentDto'];
export type RevenueExplanationIn = Schemas['RevenueExplanationIn'];
export type RevenueDecisionIn = Schemas['RevenueDecisionIn'];
export type NonRevenueActivityDto = Schemas['NonRevenueActivityDto'];
export type NonRevenueApprovalDto = Schemas['NonRevenueApprovalDto'];
export type NonRevenueApprovalIn = Schemas['NonRevenueApprovalIn'];
export type NonRevenueDecisionIn = Schemas['NonRevenueDecisionIn'];
