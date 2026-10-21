/** Display helpers for managed-service mandates (shared by the shell and the mandate pages). */

const SCOPE_LABELS: Readonly<Record<string, string>> = {
  FULL: 'Full management',
  OPERATIONS: 'Operations only',
};

export function mandateScopeLabel(scope: string): string {
  return SCOPE_LABELS[scope] ?? scope;
}

export function mandateLostMessage(clientName: string | null): string {
  return `The managed-service mandate for ${clientName ?? 'this client'} is no longer in force.`;
}
