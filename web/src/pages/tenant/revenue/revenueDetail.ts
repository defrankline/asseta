/** Readers of a revenue difference's free-form `detail` JSON (jobs and money sources), defensively. */
import type { SheetMoneySourceDto } from '../../../api/types';

const asText = (v: unknown): string | null =>
  typeof v === 'string' ? v : typeof v === 'number' ? String(v) : null;

/** `detail.money_sources` of a revenue difference (free-form JSON), keeping only well-formed rows. */
export function parseMoneySources(
  detail: Readonly<Record<string, unknown>>,
): SheetMoneySourceDto[] {
  const raw = detail.money_sources;
  if (!Array.isArray(raw)) return [];
  const out: SheetMoneySourceDto[] = [];
  for (const item of raw as unknown[]) {
    if (typeof item !== 'object' || item === null) continue;
    const r = item as Record<string, unknown>;
    const source = r.source === 'PREPAID_CONSUMPTION' ? 'PREPAID_CONSUMPTION' : 'INVOICE_LINE';
    const [ref, parent, job, currency, amount] = [
      asText(r.ref_id),
      asText(r.parent_id),
      asText(r.job_id),
      asText(r.currency),
      asText(r.amount),
    ];
    if (ref === null || parent === null || job === null || currency === null || amount === null)
      continue;
    out.push({
      source,
      ref_id: ref,
      parent_id: parent,
      job_id: job,
      job_number: asText(r.job_number),
      currency,
      amount,
      hours: asText(r.hours),
    });
  }
  return out;
}

export interface DifferenceJob {
  job_id: string;
  job_number: string | null;
  currency: string;
  expected: string;
  in_progress: string;
  attributed: string;
  completed: boolean;
}

/** `detail.jobs` of a revenue difference: expected and attributed money per job. */
export function parseDifferenceJobs(detail: Readonly<Record<string, unknown>>): DifferenceJob[] {
  const raw = detail.jobs;
  if (!Array.isArray(raw)) return [];
  const out: DifferenceJob[] = [];
  for (const item of raw as unknown[]) {
    if (typeof item !== 'object' || item === null) continue;
    const r = item as Record<string, unknown>;
    const id = asText(r.job_id);
    const currency = asText(r.currency);
    if (id === null || currency === null) continue;
    out.push({
      job_id: id,
      job_number: asText(r.job_number),
      currency,
      expected: asText(r.expected) ?? '0',
      in_progress: asText(r.in_progress) ?? '0',
      attributed: asText(r.attributed) ?? '0',
      completed: r.completed === true,
    });
  }
  return out;
}
