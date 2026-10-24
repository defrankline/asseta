import type {
  AttachmentDto,
  AttachmentUploadIn,
  CaptureResultDto,
  ExceptionDto,
  MeterCaptureDto,
  MeterCaptureIn,
  Page,
  PhotoUrlDto,
  ResetDto,
  ResetIn,
  ReviewIn,
} from '../types';
import {
  attachmentSchema,
  captureResultSchema,
  exceptionSchema,
  meterCaptureSchema,
  photoUrlSchema,
  resetSchema,
} from './meterSchemas';
import {
  seg,
  tenantGet,
  tenantList,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

const exceptionPageSchema = tenantPageSchema(exceptionSchema);
const capturePageSchema = tenantPageSchema(meterCaptureSchema);

/** Evidence purposes accepted by uploadAttachment. */
export type AttachmentPurpose = 'METER_PHOTO' | 'SIGNATURE' | 'RESET_EVIDENCE';

export const meterService = {
  /** POST /tenant/attachments (uploadAttachment), multipart `file` + `purpose`. */
  upload(file: File, purpose: AttachmentPurpose, idempotencyKey: string): Promise<AttachmentDto> {
    const fields: Record<keyof AttachmentUploadIn, string | Blob> = { file, purpose };
    const form = new FormData();
    for (const [k, v] of Object.entries(fields)) form.append(k, v);
    return tenantSend(
      'post',
      '/tenant/attachments',
      form,
      attachmentSchema,
      'attachment',
      idempotencyKey,
    );
  },
  /** GET /tenant/attachments/{id}/url (getAttachmentUrl): short-lived signed URL; fetch on demand. */
  attachmentUrl(attachmentId: string, signal?: AbortSignal): Promise<PhotoUrlDto> {
    return tenantGet(
      `/tenant/attachments/${seg(attachmentId)}/url`,
      photoUrlSchema,
      'attachment URL',
      signal,
    );
  },
  /** POST /tenant/meter-captures (submitMeterCapture); `id` is the capture's idempotency key. */
  submitCapture(body: MeterCaptureIn, idempotencyKey: string): Promise<CaptureResultDto> {
    return tenantSend(
      'post',
      '/tenant/meter-captures',
      body,
      captureResultSchema,
      'meter capture',
      idempotencyKey,
    );
  },
  /** GET /tenant/jobs/{id}/meter-captures (listJobCaptures). */
  listCaptures(jobId: string, signal?: AbortSignal): Promise<MeterCaptureDto[]> {
    return tenantList(
      `/tenant/jobs/${seg(jobId)}/meter-captures`,
      meterCaptureSchema,
      'meter captures',
      signal,
    );
  },
  /**
   * GET /tenant/meter-captures (listMeterCaptures), latest first. Filters: `job_id`, `machine_id`,
   * `kind`, `state`, `captured_from`, `captured_to`, `mine`.
   */
  listAllCaptures(query: TenantListQuery, signal?: AbortSignal): Promise<Page<MeterCaptureDto>> {
    return tenantPage('/tenant/meter-captures', capturePageSchema, query, 'meter captures', signal);
  },
  /** POST /tenant/meter-resets (requestMeterReset). */
  requestReset(body: ResetIn, idempotencyKey: string): Promise<ResetDto> {
    return tenantSend(
      'post',
      '/tenant/meter-resets',
      body,
      resetSchema,
      'meter reset',
      idempotencyKey,
    );
  },
  /** GET /tenant/meter-resets (listMeterResets). Filters: `machine_id`, `status`, `mine`. */
  listResets(
    filters: {
      machine_id?: string | undefined;
      status?: string | undefined;
      mine?: string | undefined;
    },
    signal?: AbortSignal,
  ): Promise<ResetDto[]> {
    return tenantList('/tenant/meter-resets', resetSchema, 'meter resets', signal, filters);
  },
  /** POST /tenant/meter-resets/{id}/decision (decideMeterReset): EXPLAINED approves, CONFIRMED rejects. */
  decideReset(resetId: string, body: ReviewIn, idempotencyKey: string): Promise<ResetDto> {
    return tenantSend(
      'post',
      `/tenant/meter-resets/${seg(resetId)}/decision`,
      body,
      resetSchema,
      'meter reset',
      idempotencyKey,
    );
  },
  /** GET /tenant/exceptions (listJobExceptions). Filters: `status`, `exception_type`, `job_id`. */
  listExceptions(query: TenantListQuery, signal?: AbortSignal): Promise<Page<ExceptionDto>> {
    return tenantPage('/tenant/exceptions', exceptionPageSchema, query, 'exception page', signal);
  },
  /** POST /tenant/exceptions/{id}/review (reviewJobException). */
  reviewException(
    exceptionId: string,
    body: ReviewIn,
    idempotencyKey: string,
  ): Promise<ExceptionDto> {
    return tenantSend(
      'post',
      `/tenant/exceptions/${seg(exceptionId)}/review`,
      body,
      exceptionSchema,
      'exception',
      idempotencyKey,
    );
  },
};
