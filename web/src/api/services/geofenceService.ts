import type {
  GeofenceDto,
  GeofenceIn,
  JobSiteDto,
  JobSiteIn,
  JobSiteUpdateIn,
  LifecycleChangeIn,
} from '../types';
import { geofenceSchema, jobSiteSchema } from './geoSchemas';
import {
  inactiveParam,
  seg,
  tenantGet,
  tenantLifecycle,
  tenantList,
  tenantSend,
} from './tenantRequest';

const site = (id: string) => `/tenant/job-sites/${seg(id)}`;
const fence = (id: string) => `/tenant/geofences/${seg(id)}`;

export const geofenceService = {
  /** GET /tenant/job-sites (listJobSites); `q` searches code and name; inactive when asked for. */
  listJobSites(signal?: AbortSignal, q?: string, includeInactive?: boolean): Promise<JobSiteDto[]> {
    return tenantList('/tenant/job-sites', jobSiteSchema, 'job sites', signal, {
      q,
      ...inactiveParam(includeInactive),
    });
  },
  /** POST /tenant/job-sites (createJobSite). */
  createJobSite(body: JobSiteIn, idempotencyKey: string): Promise<JobSiteDto> {
    return tenantSend('post', '/tenant/job-sites', body, jobSiteSchema, 'job site', idempotencyKey);
  },
  /** GET /tenant/geofences (listGeofences); inactive geofences only when asked for. */
  list(signal?: AbortSignal, includeInactive?: boolean): Promise<GeofenceDto[]> {
    return tenantList('/tenant/geofences', geofenceSchema, 'geofences', signal, {
      ...inactiveParam(includeInactive),
    });
  },
  /** POST /tenant/geofences (createGeofence). */
  create(body: GeofenceIn, idempotencyKey: string): Promise<GeofenceDto> {
    return tenantSend(
      'post',
      '/tenant/geofences',
      body,
      geofenceSchema,
      'geofence',
      idempotencyKey,
    );
  },
  /** PUT /tenant/geofences/{id} (updateGeofence). */
  update(geofenceId: string, body: GeofenceIn, idempotencyKey: string): Promise<GeofenceDto> {
    return tenantSend(
      'put',
      `/tenant/geofences/${seg(geofenceId)}`,
      body,
      geofenceSchema,
      'geofence',
      idempotencyKey,
    );
  },
  /** GET /tenant/job-sites/{id} (getJobSite). */
  getJobSite(siteId: string, signal?: AbortSignal): Promise<JobSiteDto> {
    return tenantGet(site(siteId), jobSiteSchema, 'job site', signal);
  },
  /** PUT /tenant/job-sites/{id} (updateJobSite); centre editable; `version` required. */
  updateJobSite(
    siteId: string,
    body: JobSiteUpdateIn,
    idempotencyKey: string,
  ): Promise<JobSiteDto> {
    return tenantSend('put', site(siteId), body, jobSiteSchema, 'job site', idempotencyKey);
  },
  /** POST /tenant/job-sites/{id}/deactivate (deactivateJobSite). */
  deactivateJobSite(id: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return tenantLifecycle(
      `${site(id)}/deactivate`,
      body,
      jobSiteSchema,
      'job site',
      idempotencyKey,
    );
  },
  /** POST /tenant/job-sites/{id}/reactivate (reactivateJobSite). */
  reactivateJobSite(id: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return tenantLifecycle(
      `${site(id)}/reactivate`,
      body,
      jobSiteSchema,
      'job site',
      idempotencyKey,
    );
  },
  /** GET /tenant/geofences/{id} (getGeofence). */
  get(geofenceId: string, signal?: AbortSignal): Promise<GeofenceDto> {
    return tenantGet(fence(geofenceId), geofenceSchema, 'geofence', signal);
  },
  /** POST /tenant/geofences/{id}/deactivate (deactivateGeofence). */
  deactivate(id: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return tenantLifecycle(
      `${fence(id)}/deactivate`,
      body,
      geofenceSchema,
      'geofence',
      idempotencyKey,
    );
  },
  /** POST /tenant/geofences/{id}/reactivate (reactivateGeofence). */
  reactivate(id: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return tenantLifecycle(
      `${fence(id)}/reactivate`,
      body,
      geofenceSchema,
      'geofence',
      idempotencyKey,
    );
  },
};
