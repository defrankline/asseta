import type {
  AreaDto,
  AreaIn,
  AssignIn,
  AssignmentDto,
  CategoryDto,
  CategoryIn,
  EndAssignmentIn,
  MachineCreateIn,
  MachineDto,
  MachineUpdateIn,
  Page,
  TrackerAssignmentDto,
} from '../types';
import { areaSchema, assignmentSchema, categorySchema, machineSchema } from './fleetSchemas';
import {
  seg,
  tenantGet,
  tenantList,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';
import { trackerAssignmentSchema } from './trackerSchemas';

const machinePageSchema = tenantPageSchema(machineSchema);
const m = (id: string) => `/tenant/machines/${seg(id)}`;

export const machineService = {
  /** GET /tenant/machines (listMachines). Filters: `status`, `category_id`. */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<MachineDto>> {
    return tenantPage('/tenant/machines', machinePageSchema, query, 'machine page', signal);
  },
  /** GET /tenant/machines/{id} (getMachine). */
  get(machineId: string, signal?: AbortSignal): Promise<MachineDto> {
    return tenantGet(m(machineId), machineSchema, 'machine', signal);
  },
  /** POST /tenant/machines (createMachine). */
  create(body: MachineCreateIn, idempotencyKey: string): Promise<MachineDto> {
    return tenantSend('post', '/tenant/machines', body, machineSchema, 'machine', idempotencyKey);
  },
  /** PUT /tenant/machines/{id} (updateMachine); `version` guards against lost updates. */
  update(machineId: string, body: MachineUpdateIn, idempotencyKey: string): Promise<MachineDto> {
    return tenantSend('put', m(machineId), body, machineSchema, 'machine', idempotencyKey);
  },
  /** GET /tenant/machine-categories. */
  listCategories(signal?: AbortSignal): Promise<CategoryDto[]> {
    return tenantList('/tenant/machine-categories', categorySchema, 'categories', signal);
  },
  /** POST /tenant/machine-categories. */
  createCategory(body: CategoryIn, idempotencyKey: string): Promise<CategoryDto> {
    return tenantSend(
      'post',
      '/tenant/machine-categories',
      body,
      categorySchema,
      'category',
      idempotencyKey,
    );
  },
  /** GET /tenant/operating-areas. */
  listAreas(signal?: AbortSignal): Promise<AreaDto[]> {
    return tenantList('/tenant/operating-areas', areaSchema, 'operating areas', signal);
  },
  /** POST /tenant/operating-areas. */
  createArea(body: AreaIn, idempotencyKey: string): Promise<AreaDto> {
    return tenantSend(
      'post',
      '/tenant/operating-areas',
      body,
      areaSchema,
      'operating area',
      idempotencyKey,
    );
  },
  /** GET /tenant/machines/{id}/assignments (listAssignments). */
  listAssignments(machineId: string, signal?: AbortSignal): Promise<AssignmentDto[]> {
    return tenantList(`${m(machineId)}/assignments`, assignmentSchema, 'assignments', signal);
  },
  /** POST /tenant/machines/{id}/assignments (assignStaff). */
  assignStaff(machineId: string, body: AssignIn, idempotencyKey: string): Promise<AssignmentDto> {
    return tenantSend(
      'post',
      `${m(machineId)}/assignments`,
      body,
      assignmentSchema,
      'assignment',
      idempotencyKey,
    );
  },
  /** POST /tenant/assignments/{id}/end (endAssignment). */
  endAssignment(
    assignmentId: string,
    body: EndAssignmentIn,
    idempotencyKey: string,
  ): Promise<AssignmentDto> {
    return tenantSend(
      'post',
      `/tenant/assignments/${seg(assignmentId)}/end`,
      body,
      assignmentSchema,
      'assignment',
      idempotencyKey,
    );
  },
  /** GET /tenant/machines/{id}/trackers (listMachineTrackerAssignments). */
  listTrackerAssignments(machineId: string, signal?: AbortSignal): Promise<TrackerAssignmentDto[]> {
    return tenantList(
      `${m(machineId)}/trackers`,
      trackerAssignmentSchema,
      'tracker assignments',
      signal,
    );
  },
};
