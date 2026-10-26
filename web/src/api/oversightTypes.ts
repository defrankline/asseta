/**
 * Oversight (DEC-031 Phase 5) contract types: people scorecard, unbilled work, idle machines and site
 * check-ins. Aliases of ./generated/schema.ts so contract drift fails `npm run typecheck`.
 */
import type { components } from './generated/schema';

type Schemas = components['schemas'];

export type ScorecardItem = Schemas['ScorecardItem'];
export type ScorecardRecordItem = Schemas['ScorecardRecordDto']['item'];
export type AmountByCurrencyDto = Schemas['AmountByCurrencyDto'];
export type CashHeldDto = Schemas['CashHeldDto'];
export type ScorecardRowDto = Schemas['ScorecardRowDto'];
export type ScorecardRecordDto = Schemas['ScorecardRecordDto'];
export type ScorecardDetailDto = Schemas['ScorecardDetailDto'];
export type UnbilledJobDto = Schemas['UnbilledJobDto'];
export type IdleMachineDto = Schemas['IdleMachineDto'];
export type SiteCheckinIn = Schemas['SiteCheckinIn'];
export type SiteCheckinDto = Schemas['SiteCheckinDto'];
export type CheckinSlotDto = Schemas['CheckinSlotDto'];
export type CheckinSlotStatus = CheckinSlotDto['status'];
export type MySiteCheckinsDto = Schemas['MySiteCheckinsDto'];
