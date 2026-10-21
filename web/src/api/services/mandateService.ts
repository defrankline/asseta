import { array } from 'yup';
import { apiClient } from '../client';
import type {
  AssignableRoleDto,
  MandateAssignmentIn,
  MandateCloseIn,
  MandateDetailDto,
  MandateDto,
  MandateGrantIn,
  PlatformStaffDto,
} from '../types';
import { parseResponse } from '../validation';
import {
  assignableRoleSchema,
  mandateDetailSchema,
  mandateSchema,
  platformStaffSchema,
} from './mandateSchemas';

const base = '/platform/mandates';
const seg = (value: string) => encodeURIComponent(value);
const withSignal = (signal?: AbortSignal) => (signal ? { signal } : undefined);
/** Optional text search (`q`), omitted when blank. */
const searchOptions = (q: string | undefined, signal?: AbortSignal) => ({
  ...(q !== undefined && q.trim() !== '' ? { params: { q: q.trim() } } : {}),
  ...(signal ? { signal } : {}),
});

/** Platform side of the managed service: grant, staff and end client mandates. */
export const mandateService = {
  /** GET /platform/mandates (listMandates). */
  async list(signal?: AbortSignal): Promise<MandateDto[]> {
    const data = await apiClient.get<unknown>(base, withSignal(signal));
    return parseResponse(array(mandateSchema).required(), data, 'mandate list');
  },

  /** GET /platform/mandates/{id} (getMandate). */
  async get(mandateId: string, signal?: AbortSignal): Promise<MandateDetailDto> {
    const data = await apiClient.get<unknown>(`${base}/${seg(mandateId)}`, withSignal(signal));
    return parseResponse(mandateDetailSchema, data, 'mandate');
  },

  /** POST /platform/mandates (grantMandate). MANDATE_ALREADY_ACTIVE when one is in force. */
  async grant(body: MandateGrantIn, idempotencyKey: string): Promise<MandateDetailDto> {
    const data = await apiClient.post<unknown>(base, body, { idempotencyKey });
    return parseResponse(mandateDetailSchema, data, 'mandate');
  },

  /** GET /platform/mandates/staff: assignable platform staff; `q` searches name and email. */
  async listStaff(signal?: AbortSignal, q?: string): Promise<PlatformStaffDto[]> {
    const data = await apiClient.get<unknown>(`${base}/staff`, searchOptions(q, signal));
    return parseResponse(array(platformStaffSchema).required(), data, 'platform staff');
  },

  /** GET /platform/mandates/{id}/roles: client roles allowed by the scope; `q` searches the key. */
  async listRoles(
    mandateId: string,
    signal?: AbortSignal,
    q?: string,
  ): Promise<AssignableRoleDto[]> {
    const data = await apiClient.get<unknown>(
      `${base}/${seg(mandateId)}/roles`,
      searchOptions(q, signal),
    );
    return parseResponse(array(assignableRoleSchema).required(), data, 'mandate roles');
  },

  /** POST /platform/mandates/{id}/assignments (assignMandateStaff). */
  async assign(
    mandateId: string,
    body: MandateAssignmentIn,
    idempotencyKey: string,
  ): Promise<MandateDetailDto> {
    const data = await apiClient.post<unknown>(`${base}/${seg(mandateId)}/assignments`, body, {
      idempotencyKey,
    });
    return parseResponse(mandateDetailSchema, data, 'mandate');
  },

  /** POST /platform/mandates/{id}/assignments/{assignment_id}/remove (removeMandateStaff). */
  async removeAssignment(
    mandateId: string,
    assignmentId: string,
    idempotencyKey: string,
  ): Promise<MandateDetailDto> {
    const data = await apiClient.post<unknown>(
      `${base}/${seg(mandateId)}/assignments/${seg(assignmentId)}/remove`,
      {},
      { idempotencyKey },
    );
    return parseResponse(mandateDetailSchema, data, 'mandate');
  },

  /** POST /platform/mandates/{id}/end (endMandate). STALE_VERSION when the mandate changed. */
  async end(
    mandateId: string,
    body: MandateCloseIn,
    idempotencyKey: string,
  ): Promise<MandateDetailDto> {
    const data = await apiClient.post<unknown>(`${base}/${seg(mandateId)}/end`, body, {
      idempotencyKey,
    });
    return parseResponse(mandateDetailSchema, data, 'mandate');
  },
};
