import type { FormikHelpers } from 'formik';
import { toApiError } from '../../api/ApiError';

/** Apply a failed submission to Formik: server field errors + a form-level status message. */
export function applySubmitError<V>(error: unknown, helpers: FormikHelpers<V>): void {
  const apiError = toApiError(error);
  for (const [field, issue] of Object.entries(apiError.fieldErrors())) {
    helpers.setFieldError(field, issue);
  }
  const ref = apiError.correlationId !== null ? ` (ref ${apiError.correlationId})` : '';
  helpers.setStatus(`${apiError.message}${ref}`);
}

export function statusMessage(status: unknown): string | null {
  return typeof status === 'string' && status !== '' ? status : null;
}
