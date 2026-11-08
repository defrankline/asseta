import { array, mixed } from 'yup';
import type { AttachmentDto } from '../../../api/types';

/** The attachments list of a form; `required` is the tenant policy in force (off while unknown). */
export const evidenceRule = (required: boolean) =>
  array(mixed<AttachmentDto>().required())
    .required()
    .test('required', 'Attach the supporting evidence', (v) => !required || v.length > 0);

export const evidenceIds = (evidence: readonly AttachmentDto[]): string[] =>
  evidence.map((a) => a.id);
