import { PEOPLE_BATCH, peopleService } from '../../../api/services/peopleService';

/**
 * Batched, cached display-name lookup per tenant: every name requested in the same tick goes out in one
 * request (chunks of PEOPLE_BATCH). Unknown ids (non-members) and failed lookups resolve to null.
 */
type Lookup = Promise<string | null>;

const cache = new Map<string, Map<string, Lookup>>();
const pending = new Map<string, Map<string, (name: string | null) => void>>();
let scheduled = false;

async function flushTenant(waiters: Map<string, (name: string | null) => void>): Promise<void> {
  const ids = [...waiters.keys()];
  for (let i = 0; i < ids.length; i += PEOPLE_BATCH) {
    const chunk = ids.slice(i, i + PEOPLE_BATCH);
    let names = new Map<string, string>();
    try {
      names = new Map((await peopleService.list(chunk)).map((p) => [p.user_id, p.display_name]));
    } catch {
      // A failed lookup only means the id is shown instead of a name.
    }
    for (const userId of chunk) waiters.get(userId)?.(names.get(userId) ?? null);
  }
}

function flush(): void {
  scheduled = false;
  const batches = [...pending.values()];
  pending.clear();
  for (const waiters of batches) void flushTenant(waiters);
}

/** Display name of `userId` in `tenantId`, or null when it cannot be resolved. */
export function lookupPersonName(tenantId: string, userId: string): Lookup {
  let byUser = cache.get(tenantId);
  if (byUser === undefined) {
    byUser = new Map();
    cache.set(tenantId, byUser);
  }
  const known = byUser.get(userId);
  if (known !== undefined) return known;
  const lookup = new Promise<string | null>((resolve) => {
    let waiters = pending.get(tenantId);
    if (waiters === undefined) {
      waiters = new Map();
      pending.set(tenantId, waiters);
    }
    waiters.set(userId, resolve);
  });
  byUser.set(userId, lookup);
  if (!scheduled) {
    scheduled = true;
    setTimeout(flush, 0);
  }
  return lookup;
}

/** Test hook: forget cached names. */
export function resetPersonDirectory(): void {
  cache.clear();
  pending.clear();
  scheduled = false;
}
