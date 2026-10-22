import type {
  NotificationCategory,
  NotificationRoutingChangeIn,
  NotificationRoutingDto,
  NotificationSeverity,
} from '../../api/types';

export type RoutingChannel = 'push' | 'email';
export type RoutingDraft = Readonly<Record<string, { push: boolean; email: boolean }>>;

export const CATEGORY_LABELS: Readonly<Record<NotificationCategory, string>> = {
  ACTION: 'Action needed',
  REMINDER: 'Reminders',
  ANOMALY: 'Anomalies',
  BILLING: 'Billing',
  INFO: 'Information',
};

export const SEVERITY_LABELS: Readonly<Record<NotificationSeverity, string>> = {
  INFO: 'Info',
  WARNING: 'Warning',
  CRITICAL: 'Critical',
};

export const CHANNEL_LABELS: Readonly<Record<RoutingChannel, string>> = {
  push: 'Push',
  email: 'E-mail',
};

export const SOURCE_LABELS: Readonly<Record<string, string>> = {
  USER: 'Your choice',
  TENANT_DEFAULT: 'Tenant default',
  BUILT_IN: 'Asseta default',
};

export function cellKey(category: string, severity: string): string {
  return `${category}:${severity}`;
}

/** A mandatory channel of the cell is always on and cannot be switched off. */
export function isLocked(row: NotificationRoutingDto, channel: RoutingChannel): boolean {
  return row.mandatory_channels.includes(channel === 'push' ? 'PUSH' : 'EMAIL');
}

export function effectiveCell(
  row: NotificationRoutingDto,
  draft: RoutingDraft,
): { push: boolean; email: boolean } {
  const d = draft[cellKey(row.category, row.severity)];
  return {
    push: isLocked(row, 'push') || (d?.push ?? row.push),
    email: isLocked(row, 'email') || (d?.email ?? row.email),
  };
}

/** Cells whose push/e-mail choice differs from the server: the PUT body's `changes`. */
export function routingChanges(
  rows: readonly NotificationRoutingDto[],
  draft: RoutingDraft,
): NotificationRoutingChangeIn[] {
  return rows.flatMap((row) => {
    if (draft[cellKey(row.category, row.severity)] === undefined) return [];
    const next = effectiveCell(row, draft);
    if (next.push === row.push && next.email === row.email) return [];
    return [{ category: row.category, severity: row.severity, push: next.push, email: next.email }];
  });
}
