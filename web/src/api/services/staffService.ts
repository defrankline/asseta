import type { Page, StaffDto, StaffIn } from '../types';
import { staffSchema } from './fleetSchemas';
import { tenantPage, tenantPageSchema, tenantSend, type TenantListQuery } from './tenantRequest';

const staffPageSchema = tenantPageSchema(staffSchema);

export const staffService = {
  /** GET /tenant/staff (listStaff). Filter: `kind`. */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<StaffDto>> {
    return tenantPage('/tenant/staff', staffPageSchema, query, 'staff page', signal);
  },
  /** POST /tenant/staff (createStaff). */
  create(body: StaffIn, idempotencyKey: string): Promise<StaffDto> {
    return tenantSend('post', '/tenant/staff', body, staffSchema, 'staff member', idempotencyKey);
  },
};
