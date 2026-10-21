import { customerService } from '../../../../api/services/customerService';
import { jobService } from '../../../../api/services/jobService';
import type { JobDto, JobSummaryDto } from '../../../../api/types';

/** Upper bounds for one eligibility read (pages of COMPLETED jobs / contracts). */
export const ELIGIBLE_PAGE_SIZE = 200;
export const MAX_SUMMARIES = 50;

export interface EligibleJob {
  job: JobDto;
  summary: JobSummaryDto;
  /** COMPLETED, billing-ready and priced by the server (the only invoiceable jobs). */
  billable: boolean;
}

/**
 * COMPLETED jobs of one customer with their server-priced charges (from the job summary, the single
 * pricing source). The jobs API has no customer filter, so the customer's contracts are read first and
 * COMPLETED jobs (server-searched by `q`) are matched to them. Whether a job already sits on another
 * non-voided invoice is only known to the server (JOB_ALREADY_INVOICED on drafting).
 */
export async function loadEligibleJobs(
  customerId: string,
  q: string,
  signal: AbortSignal,
): Promise<EligibleJob[]> {
  const contracts = await customerService.listContracts(
    {
      page: 1,
      page_size: ELIGIBLE_PAGE_SIZE,
      filters: { customer_id: customerId, include_inactive: 'true' },
    },
    signal,
  );
  const contractIds = new Set(contracts.items.map((c) => c.id));
  if (contractIds.size === 0) return [];
  const jobs = await jobService.list(
    { page: 1, page_size: ELIGIBLE_PAGE_SIZE, q, filters: { status: 'COMPLETED' } },
    signal,
  );
  const mine = jobs.items.filter((j) => contractIds.has(j.contract_id)).slice(0, MAX_SUMMARIES);
  const summaries = await Promise.all(mine.map((j) => jobService.summary(j.id, signal)));
  return summaries.map((summary, i) => ({
    job: mine[i] ?? summary.job,
    summary,
    billable: summary.billing_ready && summary.charges != null,
  }));
}
