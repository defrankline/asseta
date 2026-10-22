export interface BackoffOptions {
  /** First retry delay (default 1 s). */
  baseMs?: number;
  /** Ceiling (default 30 s). */
  maxMs?: number;
  factor?: number;
  /**
   * Share of the delay that is randomised (0–1, default 0.5): the delay is
   * `exp × (1 − jitter) + random × exp × jitter`, so many tabs reconnecting after an outage spread out.
   */
  jitter?: number;
}

export const DEFAULT_BACKOFF: Required<BackoffOptions> = {
  baseMs: 1_000,
  maxMs: 30_000,
  factor: 2,
  jitter: 0.5,
};

/** Exponential backoff with jitter for reconnect attempt `attempt` (0-based). */
export function backoffDelay(
  attempt: number,
  options: BackoffOptions = {},
  random: () => number = Math.random,
): number {
  const { baseMs, maxMs, factor, jitter } = { ...DEFAULT_BACKOFF, ...options };
  const exp = Math.min(maxMs, baseMs * factor ** Math.max(0, attempt));
  const share = Math.min(1, Math.max(0, jitter));
  const r = Math.min(1, Math.max(0, random()));
  return Math.round(exp * (1 - share) + r * exp * share);
}
