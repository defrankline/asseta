import { object } from 'yup';
import type { PersonDto } from '../types';
import { id, text } from './schemaKit';
import { tenantList } from './tenantRequest';

/** At most this many ids per request (server limit). */
export const PEOPLE_BATCH = 100;

const personSchema = object({ user_id: id(), display_name: text() });

/** Colleagues' display names in the active tenant (never e-mail; non-members resolve to nothing). */
export const peopleService = {
  /** GET /tenant/people?ids=a,b (listTenantPeople). */
  list(ids: readonly string[], signal?: AbortSignal): Promise<PersonDto[]> {
    return tenantList('/tenant/people', personSchema, 'people', signal, { ids: ids.join(',') });
  },
  /** GET /tenant/people?q= (listTenantPeople): current members by name, for pickers (at most 20). */
  search(q: string, signal?: AbortSignal): Promise<PersonDto[]> {
    return tenantList('/tenant/people', personSchema, 'people', signal, { q });
  },
};
