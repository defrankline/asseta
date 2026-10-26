import { revenueService } from '../../../api/services/revenueService';
import type { RevenueReasonDto } from '../../../api/types';
import { LOOKUP_PAGE_SIZE } from '../../../components/data/AsyncAutocomplete';

/** Server-backed lookups for revenue forms (the typed text is passed to the API as `q`). */

export const revenueReasonLabel = (r: RevenueReasonDto): string => `${r.code} · ${r.name}`;

/** Active entries of the tenant's revenue reason list. */
export const searchRevenueReasons = async (
  q: string,
  signal: AbortSignal,
): Promise<RevenueReasonDto[]> =>
  (await revenueService.listReasons({ page: 1, page_size: LOOKUP_PAGE_SIZE, q }, signal)).items;

export const resolveRevenueReason = async (
  id: string,
  signal: AbortSignal,
): Promise<RevenueReasonDto | null> => revenueService.getReason(id, signal);
