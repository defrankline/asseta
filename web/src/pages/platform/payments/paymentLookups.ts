import { platformInvoiceService } from '../../../api/services/platformInvoiceService';
import type { InvoiceDto, InvoiceLineDto } from '../../../api/types';
import { LOOKUP_PAGE_SIZE } from '../../../components/data/AsyncAutocomplete';
import { compareDecimal, formatMoney, isZeroDecimal, sumDecimals } from '../../../utils/money';

/** Server lookups for the payment dialogs (typed text sent as `q`). */

export const invoiceId = (i: InvoiceDto): string => i.id ?? '';
export const invoiceLabel = (i: InvoiceDto): string =>
  `${i.invoice_number ?? 'Invoice'} · balance ${formatMoney(i.balance, i.currency)}`;

/** The tenant's invoices that still take money (not void, balance above zero). */
export const searchOpenInvoices =
  (tenantId: string) =>
  async (q: string, signal: AbortSignal): Promise<InvoiceDto[]> =>
    (
      await platformInvoiceService.list(
        { page: 1, page_size: LOOKUP_PAGE_SIZE, tenant_id: tenantId, q },
        signal,
      )
    ).items.filter((i) => i.id !== null && i.status !== 'VOIDED' && !isZeroDecimal(i.balance));

export const resolveInvoice = (id: string, signal: AbortSignal) =>
  platformInvoiceService.get(id, signal);

/** Remaining payable of a line (exact decimal subtraction, for the form check only). */
export function lineRemaining(line: InvoiceLineDto): string | null {
  if (line.payable == null || line.id == null) return null;
  const remaining = sumDecimals([line.payable, `-${line.paid ?? '0'}`]);
  return compareDecimal(remaining, '0') > 0 ? remaining : null;
}
