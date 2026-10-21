import type { LifecycleChangeIn, Page, StaffDto, StaffIn, StaffUpdateIn } from '../types';
import { staffSchema } from './fleetSchemas';
import {
  type TenantListQuery,
  seg,
  tenantGet,
  tenantLifecycle,
  tenantPage,
  tenantPageSchema,
  tenantSend,
} from './tenantRequest';

const staffPageSchema = tenantPageSchema(staffSchema);
const one = (id: string) => `/tenant/staff/${seg(id)}`;

export const staffService = {
  /** GET /tenant/staff (listStaff). Filters: `kind`, `include_inactive`; `q` also matches employee code. */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<StaffDto>> {
    return tenantPage('/tenant/staff', staffPageSchema, query, 'staff page', signal);
  },
  /** POST /tenant/staff (createStaff). */
  create(body: StaffIn, idempotencyKey: string): Promise<StaffDto> {
    return tenantSend('post', '/tenant/staff', body, staffSchema, 'staff member', idempotencyKey);
  },
  /** GET /tenant/staff/{id} (getStaff). */
  get(staffId: string, signal?: AbortSignal): Promise<StaffDto> {
    return tenantGet(one(staffId), staffSchema, 'staff member', signal);
  },
  /** PUT /tenant/staff/{id} (updateStaff); `version` required. */
  update(staffId: string, body: StaffUpdateIn, idempotencyKey: string): Promise<StaffDto> {
    return tenantSend('put', one(staffId), body, staffSchema, 'staff member', idempotencyKey);
  },
  /** POST /tenant/staff/{id}/deactivate (deactivateStaff); ends open machine assignments. */
  deactivate(id: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return tenantLifecycle(
      `${one(id)}/deactivate`,
      body,
      staffSchema,
      'staff member',
      idempotencyKey,
    );
  },
  /** POST /tenant/staff/{id}/reactivate (reactivateStaff). */
  reactivate(id: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return tenantLifecycle(
      `${one(id)}/reactivate`,
      body,
      staffSchema,
      'staff member',
      idempotencyKey,
    );
  },
};
