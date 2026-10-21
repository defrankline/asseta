import { ValidationError, type Schema } from 'yup';
import { ApiError } from './ApiError';

/** Runtime-validate a response body against a Yup schema; throws a typed ApiError on mismatch. */
export function parseResponse<T>(schema: Schema<T>, data: unknown, what: string): T {
  try {
    return schema.validateSync(data, { abortEarly: false, stripUnknown: false });
  } catch (err) {
    const issues = err instanceof ValidationError ? err.errors : [String(err)];
    throw new ApiError({
      status: null,
      code: 'contract_mismatch',
      message: `The server returned an unexpected ${what} payload.`,
      correlationId: null,
      details: issues.map((issue) => ({ field: null, issue })),
    });
  }
}
