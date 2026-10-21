import { LOOKUP_PAGE_SIZE } from '../../../components/data/AsyncAutocomplete';
import { mandateService } from '../../../api/services/mandateService';
import { tenantService } from '../../../api/services/tenantService';
import type { AssignableRoleDto, PlatformStaffDto, TenantDto } from '../../../api/types';

/** Server lookups for platform autocompletes; the typed text is sent as `q`. */

export const tenantId = (t: TenantDto): string => t.id;
export const tenantLabel = (t: TenantDto): string => t.display_name;
export const searchTenants = async (q: string, signal: AbortSignal) =>
  (await tenantService.list({ page: 1, page_size: LOOKUP_PAGE_SIZE, sort: 'name', q }, signal))
    .items;
export const resolveTenant = (id: string, signal: AbortSignal) => tenantService.get(id, signal);

export const staffId = (s: PlatformStaffDto): string => s.user_id;
export const staffLabel = (s: PlatformStaffDto): string => `${s.display_name} (${s.email})`;
export const searchPlatformStaff = (q: string, signal: AbortSignal) =>
  mandateService.listStaff(signal, q);

export const roleKey = (r: AssignableRoleDto): string => r.key;
/** Client roles the mandate's scope allows, searched by key. */
export const roleSearch = (mandateId: string) => (q: string, signal: AbortSignal) =>
  mandateService.listRoles(mandateId, signal, q);
