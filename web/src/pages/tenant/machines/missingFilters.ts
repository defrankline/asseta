import { machineService } from '../../../api/services/machineService';
import { trackerService } from '../../../api/services/trackerService';
import type { MachineDto, Page } from '../../../api/types';
import type { ServerQuery } from '../../../components/data/useServerPage';

/** `?missing=…` views of the machine list (links from the go-live checklist). */
export type MissingView = 'tracker' | 'enrollment';

export function missingViewOf(raw: string | null): MissingView | null {
  return raw === 'tracker' || raw === 'enrollment' ? raw : null;
}

const BATCH = 200;

/** Every item of a paged list (the API caps a page at 200). */
async function fetchAll<T>(fetch: (page: number) => Promise<Page<T>>): Promise<T[]> {
  const out: T[] = [];
  for (let page = 1; ; page += 1) {
    const result = await fetch(page);
    out.push(...result.items);
    if (result.items.length === 0 || out.length >= result.total) return out;
  }
}

/**
 * Active machines without a main tracker fitted now. The machine list cannot filter on trackers,
 * so this reads the active machines and the trackers' current assignments and pages locally.
 */
export async function fetchMachinesWithoutTracker(
  query: ServerQuery,
  signal: AbortSignal,
): Promise<Page<MachineDto>> {
  const [machines, trackers] = await Promise.all([
    fetchAll((page) =>
      machineService.list(
        { page, page_size: BATCH, q: query.q, filters: { status: 'ACTIVE' } },
        signal,
      ),
    ),
    fetchAll((page) => trackerService.list({ page, page_size: BATCH }, signal)),
  ]);
  const tracked = new Set(
    trackers.flatMap((t) => {
      const a = t.current_assignment;
      return a != null && a.is_primary && a.effective_to === null ? [a.machine_id] : [];
    }),
  );
  const missing = machines.filter((m) => !tracked.has(m.id));
  const start = (query.page - 1) * query.page_size;
  return {
    items: missing.slice(start, start + query.page_size),
    total: missing.length,
    page: query.page,
    page_size: query.page_size,
  };
}
