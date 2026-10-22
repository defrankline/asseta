import type { NotificationPreferenceChangeIn, NotificationPreferenceDto } from '../../api/types';

export type Channels = Pick<NotificationPreferenceDto, 'in_app' | 'sms'>;
export type Channel = keyof Channels;
export type Draft = Readonly<Record<string, Channels>>;

/** Backend channel codes in `mandatory_channels`. */
const CHANNEL_CODE: Readonly<Record<Channel, string>> = { in_app: 'IN_APP', sms: 'SMS' };

export const MANDATORY_HINT = 'Required: always delivered on this channel.';
export const LOW_PRIORITY_HINT = 'Low priority: SMS is sent only if you switch it on.';

/** The channel cannot be switched off (mandatory) or SMS is not offered for this type. */
export function isLocked(p: NotificationPreferenceDto, channel: Channel): boolean {
  if (p.mandatory_channels.includes(CHANNEL_CODE[channel])) return true;
  return channel === 'sms' && !p.sms_available;
}

export function effective(p: NotificationPreferenceDto, draft: Draft): Channels {
  const d = draft[p.type];
  if (d === undefined) return { in_app: p.in_app, sms: p.sms };
  // Locked channels always keep the server value.
  return {
    in_app: isLocked(p, 'in_app') ? p.in_app : d.in_app,
    sms: isLocked(p, 'sms') ? p.sms : d.sms,
  };
}

/** Changed preferences only; locked channels are never changed (the server refuses them). */
export function preferenceChanges(
  prefs: readonly NotificationPreferenceDto[],
  draft: Draft,
): NotificationPreferenceChangeIn[] {
  return prefs
    .map((p) => ({ p, next: effective(p, draft) }))
    .filter(({ p, next }) => p.in_app !== next.in_app || p.sms !== next.sms)
    .map(({ p, next }) => ({ type: p.type, ...next }));
}

export function groupByCategory(prefs: readonly NotificationPreferenceDto[]) {
  const groups = new Map<string, NotificationPreferenceDto[]>();
  for (const p of prefs) groups.set(p.category, [...(groups.get(p.category) ?? []), p]);
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

const CATEGORY_LABELS: Readonly<Record<string, string>> = {
  ACTION: 'Actions to take',
  REMINDER: 'Reminders',
  ANOMALY: 'Anomalies',
  BILLING: 'Billing',
  INFO: 'Information',
};

export function categoryLabel(code: string): string {
  return CATEGORY_LABELS[code] ?? code.charAt(0) + code.slice(1).toLowerCase().replace(/_/g, ' ');
}
