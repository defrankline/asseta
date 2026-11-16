/**
 * Oversight (DEC-031 Phase 5) contract types: people scorecard and idle machines. Aliases of
 * ./generated/schema.ts so contract drift fails `npm run typecheck`.
 */
import type { components } from './generated/schema';

type Schemas = components['schemas'];

export type ScorecardItem = Schemas['ScorecardItem'];
export type ScorecardRecordItem = Schemas['ScorecardRecordDto']['item'];
export type AmountByCurrencyDto = Schemas['AmountByCurrencyDto'];
export type CashHeldDto = Schemas['CashHeldDto'];
export type ScorecardRowDto = Schemas['ScorecardRowDto'];
export type ScorecardRecordDto = Schemas['ScorecardRecordDto'];
export interface ScorecardDetailDto {
  row: ScorecardRowDto;
  records: ScorecardRecordDto[];
}
export type IdleMachineDto = Schemas['IdleMachineDto'];
