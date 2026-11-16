/**
 * Machine reports (ADR-008): aliases of ./generated/schema.ts so contract drift fails `npm run typecheck`.
 */
import type { components } from './generated/schema';

type Schemas = components['schemas'];

export type MachineReportDto = Schemas['MachineReportDto'];
export type MachineReportLineDto = Schemas['MachineReportLineDto'];
export type MachineReportIn = Schemas['MachineReportIn'];
export type MachineReportLineIn = Schemas['MachineReportLineIn'];
export type MachineReportStatus = Schemas['MachineReportStatus'];
export type MachineReportStatusDto = Schemas['MachineReportStatusDto'];
export type MachineReportContextDto = Schemas['MachineReportContextDto'];
export type MachineReportReasonDto = Schemas['MachineReportReasonDto'];
export type MachineReportReasonIn = Schemas['MachineReportReasonIn'];
/** PUT body of a reason (shared with the engine-hour reason table). */
export type MachineReportReasonUpdateIn = Schemas['EngineHourReasonUpdateIn'];
export type MachineReportDecisionIn = Schemas['MachineReportDecisionIn'];
export type MachineReportRejectIn = Schemas['MachineReportRejectIn'];
export type AvailableHoursDto = Schemas['AvailableHoursDto'];
export type TrackerCheckDto = Schemas['TrackerCheckDto'];
export type LotDto = Schemas['LotDto'];
export type ReportLineKind = Schemas['ReportLineKind'];
export type StartSource = Schemas['StartSource'];
export type HoursScope = MachineReportContextDto['hours_scope'];
