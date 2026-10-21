import type { GeofenceDto, GeofenceIn, JobSiteDto, JobSiteIn } from '../types';
import { geofenceSchema, jobSiteSchema } from './geoSchemas';
import { seg, tenantList, tenantSend } from './tenantRequest';

export const geofenceService = {
  /** GET /tenant/job-sites (listJobSites). */
  listJobSites(signal?: AbortSignal): Promise<JobSiteDto[]> {
    return tenantList('/tenant/job-sites', jobSiteSchema, 'job sites', signal);
  },
  /** POST /tenant/job-sites (createJobSite). */
  createJobSite(body: JobSiteIn, idempotencyKey: string): Promise<JobSiteDto> {
    return tenantSend('post', '/tenant/job-sites', body, jobSiteSchema, 'job site', idempotencyKey);
  },
  /** GET /tenant/geofences (listGeofences). */
  list(signal?: AbortSignal): Promise<GeofenceDto[]> {
    return tenantList('/tenant/geofences', geofenceSchema, 'geofences', signal);
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
};
