import type { Connectivity } from '../../api/types';
import type { StatusTone } from '../display/StatusChip';

export interface ConnectivityInfo {
  label: string;
  description: string;
  tone: StatusTone;
  /** Marker colour (always paired with a text label / legend, never colour alone). */
  color: string;
}

export const CONNECTIVITY_ORDER: readonly Connectivity[] = [
  'LIVE',
  'RECENT',
  'STALE',
  'OFFLINE',
  'NEVER_REPORTED',
  'NO_TRACKER',
];

export const CONNECTIVITY_INFO: Readonly<Record<Connectivity, ConnectivityInfo>> = {
  LIVE: {
    label: 'Live',
    description: 'Tracker reporting within the live window.',
    tone: 'success',
    color: '#16a34a',
  },
  RECENT: {
    label: 'Recent',
    description: 'Reported recently, but not within the live window — last known position.',
    tone: 'info',
    color: '#2563eb',
  },
  STALE: {
    label: 'Stale',
    description: 'No report for longer than the stale threshold — last known position.',
    tone: 'warning',
    color: '#d97706',
  },
  OFFLINE: {
    label: 'Offline',
    description: 'No report for longer than the offline threshold — last known position.',
    tone: 'error',
    color: '#dc2626',
  },
  NEVER_REPORTED: {
    label: 'Never reported',
    description: 'A tracker is assigned but has never reported.',
    tone: 'default',
    color: '#6b7280',
  },
  NO_TRACKER: {
    label: 'No tracker',
    description: 'No primary tracker is assigned to this machine.',
    tone: 'default',
    color: '#9ca3af',
  },
};

export interface MarkerStyle {
  color: string;
  /** Hollow markers = last-known position, not live. */
  hollow: boolean;
  /** Fill opacity 0..1. */
  fillOpacity: number;
  /** Overall opacity; greyed when degraded. */
  opacity: number;
  /** True only for a live connection with a live-fresh position (`is_live`). */
  live: boolean;
  /** Short label for popups / screen readers, e.g. `Stale · last known`. */
  label: string;
}

/**
 * Marker style for a machine. A marker is styled as live ONLY when the server says the
 * connectivity is LIVE *and* `is_live` (position fresh within the live window). Everything else is
 * a last-known position: hollow for STALE/OFFLINE/never/no-tracker or a LIVE link with an old
 * position, faded for RECENT. Stale data is never presented as live.
 */
export function markerStyle(connectivity: Connectivity, isLive: boolean): MarkerStyle {
  const info = CONNECTIVITY_INFO[connectivity];
  if (connectivity === 'LIVE' && isLive) {
    return {
      color: info.color,
      hollow: false,
      fillOpacity: 1,
      opacity: 1,
      live: true,
      label: 'Live',
    };
  }
  if (connectivity === 'RECENT') {
    return {
      color: info.color,
      hollow: false,
      fillOpacity: 0.45,
      opacity: 0.85,
      live: false,
      label: 'Recent · last known',
    };
  }
  const greyed = connectivity !== 'LIVE' && connectivity !== 'STALE';
  return {
    color: info.color,
    hollow: true,
    fillOpacity: 0,
    opacity: greyed ? 0.6 : 0.9,
    live: false,
    label: `${info.label} · last known`,
  };
}
