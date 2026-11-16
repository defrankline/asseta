/**
 * Oversight (DEC-031 Phase 5) contract types: people scorecard and idle machines. Aliases of
 * ./generated/schema.ts so contract drift fails `npm run typecheck`.
 *
 * Site check-ins, unbilled work and job fields were retired by ADR-008: the aliases leave them out
 * so nothing here relies on fields the server no longer sends.
 */
import type { components } from './generated/schema';

type Schemas = components['schemas'];

export type ScorecardItem = Exclude<Schemas['ScorecardItem'], 'MISSED_CHECKIN'>;
export type ScorecardRecordItem = Exclude<Schemas['ScorecardRecordDto']['item'], 'MISSED_CHECKIN'>;
export type AmountByCurrencyDto = Schemas['AmountByCurrencyDto'];
export type CashHeldDto = Schemas['CashHeldDto'];
export type ScorecardRowDto = Omit<Schemas['ScorecardRowDto'], 'checkins_missed' | 'checkins_made'>;
export type ScorecardRecordDto = Omit<
  Schemas['ScorecardRecordDto'],
  'item' | 'job_id' | 'job_number'
> & { item: ScorecardRecordItem };
export interface ScorecardDetailDto {
  row: ScorecardRowDto;
  records: ScorecardRecordDto[];
}
export type IdleMachineDto = Omit<
  Schemas['IdleMachineDto'],
  | 'last_job_id'
  | 'last_job_number'
  | 'last_job_completed_at'
  | 'planned_job_id'
  | 'planned_job_number'
>;
