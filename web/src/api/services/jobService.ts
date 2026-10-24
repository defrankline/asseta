import { array } from 'yup';
import type {
  AcknowledgementDto,
  AcknowledgementIn,
  ActivityDto,
  ActivityIn,
  JobDto,
  JobIn,
  JobSummaryDto,
  JobTransitionIn,
  JobUpdateIn,
  MachineDto,
  Page,
} from '../types';
import { machineSchema } from './fleetSchemas';
import { acknowledgementSchema, activitySchema, jobSchema, jobSummarySchema } from './jobSchemas';
import {
  seg,
  tenantGet,
  tenantList,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

const jobPageSchema = tenantPageSchema(jobSchema);
const j = (id: string) => `/tenant/jobs/${seg(id)}`;

export const jobService = {
  /**
   * GET /tenant/jobs (listJobs). Filters: `status`, `machine_id`, `mine` ('true': jobs the caller
   * supervises); `q` searches the job number.
   */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<JobDto>> {
    return tenantPage('/tenant/jobs', jobPageSchema, query, 'job page', signal);
  },
  /** POST /tenant/jobs (createJob). */
  create(body: JobIn, idempotencyKey: string): Promise<JobDto> {
    return tenantSend('post', '/tenant/jobs', body, jobSchema, 'job', idempotencyKey);
  },
  /** GET /tenant/jobs/{id} (getJobSummary). */
  summary(jobId: string, signal?: AbortSignal): Promise<JobSummaryDto> {
    return tenantGet(j(jobId), jobSummarySchema, 'job summary', signal);
  },
  /** POST /tenant/jobs/{id}/transitions (transitionJob). */
  transition(jobId: string, body: JobTransitionIn, idempotencyKey: string): Promise<JobDto> {
    return tenantSend('post', `${j(jobId)}/transitions`, body, jobSchema, 'job', idempotencyKey);
  },
  /** GET /tenant/jobs/{id}/activities (listJobActivities). */
  listActivities(jobId: string, signal?: AbortSignal): Promise<ActivityDto[]> {
    return tenantGet(
      `${j(jobId)}/activities`,
      array(activitySchema).required(),
      'job activities',
      signal,
    );
  },
  /** POST /tenant/jobs/{id}/activities (logJobActivity); `client_id` dedupes retries. */
  logActivity(jobId: string, body: ActivityIn, idempotencyKey: string): Promise<ActivityDto> {
    return tenantSend(
      'post',
      `${j(jobId)}/activities`,
      body,
      activitySchema,
      'job activity',
      idempotencyKey,
    );
  },
  /** GET /tenant/jobs/{id}/acknowledgements (listJobAcknowledgements). */
  listAcknowledgements(jobId: string, signal?: AbortSignal): Promise<AcknowledgementDto[]> {
    return tenantGet(
      `${j(jobId)}/acknowledgements`,
      array(acknowledgementSchema).required(),
      'acknowledgements',
      signal,
    );
  },
  /** POST /tenant/jobs/{id}/acknowledgements (acknowledgeJob); `client_id` dedupes retries. */
  acknowledge(
    jobId: string,
    body: AcknowledgementIn,
    idempotencyKey: string,
  ): Promise<AcknowledgementDto> {
    return tenantSend(
      'post',
      `${j(jobId)}/acknowledgements`,
      body,
      acknowledgementSchema,
      'acknowledgement',
      idempotencyKey,
    );
  },
  /** GET /tenant/field/machines (listMyFieldMachines): machines the caller works on; `q` searches. */
  fieldMachines(q: string | undefined, signal?: AbortSignal): Promise<MachineDto[]> {
    return tenantList('/tenant/field/machines', machineSchema, 'field machines', signal, { q });
  },
  /** PUT /tenant/jobs/{id} (updateJob): DRAFT / PENDING_APPROVAL only; price is re-derived. */
  update(jobId: string, body: JobUpdateIn, idempotencyKey: string): Promise<JobDto> {
    return tenantSend('put', j(jobId), body, jobSchema, 'job', idempotencyKey);
  },
};
