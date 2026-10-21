/** RFC 4122 v4 UUID using the Web Crypto API. */
export function newUuid(): string {
  return crypto.randomUUID();
}

/**
 * Idempotency key for a mutating call. Create one per user intent (e.g. when a form dialog opens)
 * and reuse it for retries of the same submission.
 */
export function newIdempotencyKey(): string {
  return newUuid();
}
