import { useCallback, useMemo } from 'react';
import { customerPaymentService } from '../../../../api/services/financeService';
import { jobService } from '../../../../api/services/jobService';
import type { CustomerPaymentDto, HireAllocationDto, HireInvoiceDto } from '../../../../api/types';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { shortId } from '../../shared/financeDisplay';

/** Job id → job number for the invoice's jobs (read from their summaries). */
export function useInvoiceJobLabels(jobIds: readonly string[]): (id: string) => string {
  const key = jobIds.join(',');
  const load = useCallback(
    async (signal: AbortSignal) => {
      const ids = key === '' ? [] : key.split(',');
      const rows = await Promise.all(ids.map((id) => jobService.summary(id, signal)));
      return rows.map((s) => s.job);
    },
    [key],
  );
  const res = useAsyncResource(load);
  return useMemo(() => {
    const names = new Map((res.data ?? []).map((j) => [j.id, j.job_number]));
    return (id: string) => names.get(id) ?? shortId(id);
  }, [res.data]);
}

export interface InvoiceAllocation {
  payment: CustomerPaymentDto;
  allocation: HireAllocationDto;
}

/** Page size used to read a customer's payments when listing those applied to one invoice. */
export const PAYMENTS_PAGE_SIZE = 200;

/**
 * Payments allocated to this invoice (active and released). The payments API filters by customer;
 * allocations are matched to the invoice from those rows.
 */
export function useInvoiceAllocations(invoice: HireInvoiceDto | null, reloadKey = 0) {
  const customerId = invoice?.customer_id ?? '';
  const invoiceId = invoice?.id ?? '';
  const load = useCallback(
    async (signal: AbortSignal): Promise<InvoiceAllocation[]> => {
      const page = await customerPaymentService.list(
        { page: 1, page_size: PAYMENTS_PAGE_SIZE, filters: { customer_id: customerId } },
        signal,
      );
      return page.items.flatMap((payment) =>
        payment.allocations
          .filter((a) => a.invoice_id === invoiceId)
          .map((allocation) => ({ payment, allocation })),
      );
    },
    [customerId, invoiceId],
  );
  return useAsyncResource(load, [reloadKey], invoice !== null && invoice.status !== 'DRAFT');
}

/** Invoice number, or a clear "Draft" marker (drafts are not numbered until issued). */
export function invoiceTitle(i: HireInvoiceDto): string {
  return i.invoice_number ?? `Draft ${i.id.slice(0, 8)}`;
}
