import type {
  AreaDto,
  AreaIn,
  AreaUpdateIn,
  AssignIn,
  AssignmentDto,
  CategoryDto,
  CategoryIn,
  CategoryUpdateIn,
  EndAssignmentIn,
  LifecycleChangeIn,
  MachineCreateIn,
  MachineDto,
  MachineUpdateIn,
  Page,
  TrackerAssignmentDto,
} from '../types';
import { areaSchema, assignmentSchema, categorySchema, machineSchema } from './fleetSchemas';
import {
  type TenantListQuery,
  inactiveParam,
  seg,
  tenantGet,
  tenantLifecycle,
  tenantList,
  tenantPage,
  tenantPageSchema,
  tenantSend,
} from './tenantRequest';
import { trackerAssignmentSchema } from './trackerSchemas';

const machinePageSchema = tenantPageSchema(machineSchema);
const m = (id: string) => `/tenant/machines/${seg(id)}`;

export const machineService = {
  /**
   * GET /tenant/machines (listMachines). Filters: `status`, `category_id`, `include_inactive`,
   * `missing` (`tracker` | `enrollment`: active machines still lacking that go-live part).
   */
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
  /** GET /tenant/machine-categories; `q` searches the name; inactive only when asked for. */
  listCategories(
    signal?: AbortSignal,
    q?: string,
    includeInactive?: boolean,
  ): Promise<CategoryDto[]> {
    return tenantList('/tenant/machine-categories', categorySchema, 'categories', signal, {
      q,
      ...inactiveParam(includeInactive),
    });
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
  /** GET /tenant/operating-areas; `q` searches code and name; inactive only when asked for. */
  listAreas(signal?: AbortSignal, q?: string, includeInactive?: boolean): Promise<AreaDto[]> {
    return tenantList('/tenant/operating-areas', areaSchema, 'operating areas', signal, {
      q,
      ...inactiveParam(includeInactive),
    });
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
  /** POST /tenant/machines/{id}/deactivate (deactivateMachine): retire (status DISPOSED). */
  deactivate(id: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return tenantLifecycle(`${m(id)}/deactivate`, body, machineSchema, 'machine', idempotencyKey);
  },
  /** POST /tenant/machines/{id}/reactivate (reactivateMachine): reinstate a retired machine. */
  reactivate(id: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return tenantLifecycle(`${m(id)}/reactivate`, body, machineSchema, 'machine', idempotencyKey);
  },
  /** GET /tenant/machine-categories/{id} (getMachineCategory). */
  getCategory(categoryId: string, signal?: AbortSignal): Promise<CategoryDto> {
    return tenantGet(
      `/tenant/machine-categories/${seg(categoryId)}`,
      categorySchema,
      'category',
      signal,
    );
  },
  /** PUT /tenant/machine-categories/{id} (updateMachineCategory); `version` required. */
  updateCategory(
    categoryId: string,
    body: CategoryUpdateIn,
    idempotencyKey: string,
  ): Promise<CategoryDto> {
    return tenantSend(
      'put',
      `/tenant/machine-categories/${seg(categoryId)}`,
      body,
      categorySchema,
      'category',
      idempotencyKey,
    );
  },
  /** POST /tenant/machine-categories/{id}/deactivate (deactivateMachineCategory). */
  deactivateCategory(id: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return tenantLifecycle(
      `/tenant/machine-categories/${seg(id)}/deactivate`,
      body,
      categorySchema,
      'category',
      idempotencyKey,
    );
  },
  /** POST /tenant/machine-categories/{id}/reactivate (reactivateMachineCategory). */
  reactivateCategory(id: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return tenantLifecycle(
      `/tenant/machine-categories/${seg(id)}/reactivate`,
      body,
      categorySchema,
      'category',
      idempotencyKey,
    );
  },
  /** GET /tenant/operating-areas/{id} (getOperatingArea). */
  getArea(areaId: string, signal?: AbortSignal): Promise<AreaDto> {
    return tenantGet(
      `/tenant/operating-areas/${seg(areaId)}`,
      areaSchema,
      'operating area',
      signal,
    );
  },
  /** PUT /tenant/operating-areas/{id} (updateOperatingArea); `version` required. */
  updateArea(areaId: string, body: AreaUpdateIn, idempotencyKey: string): Promise<AreaDto> {
    return tenantSend(
      'put',
      `/tenant/operating-areas/${seg(areaId)}`,
      body,
      areaSchema,
      'operating area',
      idempotencyKey,
    );
  },
  /** POST /tenant/operating-areas/{id}/deactivate (deactivateOperatingArea). */
  deactivateArea(id: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return tenantLifecycle(
      `/tenant/operating-areas/${seg(id)}/deactivate`,
      body,
      areaSchema,
      'operating area',
      idempotencyKey,
    );
  },
  /** POST /tenant/operating-areas/{id}/reactivate (reactivateOperatingArea). */
  reactivateArea(id: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return tenantLifecycle(
      `/tenant/operating-areas/${seg(id)}/reactivate`,
      body,
      areaSchema,
      'operating area',
      idempotencyKey,
    );
  },
};
