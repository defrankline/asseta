/** Readers of a revenue difference's free-form `detail` JSON (money sources), defensively. */
import type { SheetMoneySourceDto } from '../../../api/types';

/** A money source as the console shows it (job fields were retired by ADR-008). */
export type MoneySourceRow = Omit<SheetMoneySourceDto, 'job_id' | 'job_number'>;

const asText = (v: unknown): string | null =>
  typeof v === 'string' ? v : typeof v === 'number' ? String(v) : null;

/** `detail.money_sources` of a revenue difference (free-form JSON), keeping only well-formed rows. */
export function parseMoneySources(detail: Readonly<Record<string, unknown>>): MoneySourceRow[] {
  const raw = detail.money_sources;
  if (!Array.isArray(raw)) return [];
  const out: MoneySourceRow[] = [];
  for (const item of raw as unknown[]) {
    if (typeof item !== 'object' || item === null) continue;
    const r = item as Record<string, unknown>;
    const source = r.source === 'PREPAID_CONSUMPTION' ? 'PREPAID_CONSUMPTION' : 'INVOICE_LINE';
    const [ref, parent, currency, amount] = [
      asText(r.ref_id),
      asText(r.parent_id),
      asText(r.currency),
      asText(r.amount),
    ];
    if (ref === null || parent === null || currency === null || amount === null) continue;
    out.push({
      source,
      ref_id: ref,
      parent_id: parent,
      currency,
      amount,
      hours: asText(r.hours),
    });
  }
  return out;
}
