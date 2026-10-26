import type { SheetFlagRefDto } from '../../../api/types';
import { recordPath } from '../../../navigation/recordRoutes';
import { engineHoursMachinePath, ROUTES } from '../../../navigation/routes';
import { withQuery } from '../../../navigation/urlFilters';

/** Where a flag's record lives (exceptions, observations, the difference itself, the ledger). */
export function flagRecordPath(ref: SheetFlagRefDto, machineId: string): string {
  switch (ref.record_type) {
    case 'revenue_difference':
      return recordPath('REVENUE_DIFFERENCE', ref.record_id);
    case 'job_exception':
      return withQuery(ROUTES.tenantExceptions, { exception_type: 'MISSING_DAILY_REPORT' });
    case 'risk_signal':
      return withQuery(ROUTES.tenantInsights, { tab: 'observations' });
    default:
      return engineHoursMachinePath(machineId);
  }
}
