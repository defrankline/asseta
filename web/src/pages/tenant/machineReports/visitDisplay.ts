import dayjs from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';

dayjs.extend(utc);
dayjs.extend(timezone);

/**
 * Time since a machine's last visit (identical wording on Android, iOS and web): null → "First visit";
 * under an hour "45 min"; under a day "5 h 20 min" / "5 h"; otherwise "1 day 3 h" / "2 days".
 * Whole units, truncated.
 */
export function formatVisitGap(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return 'First visit';
  const s = Math.max(0, Math.floor(seconds));
  if (s < 3600) return `${String(Math.floor(s / 60))} min`;
  if (s < 86400) {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return m === 0 ? `${String(h)} h` : `${String(h)} h ${String(m)} min`;
  }
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const days = `${String(d)} ${d === 1 ? 'day' : 'days'}`;
  return h === 0 ? days : `${days} ${String(h)} h`;
}

/** A visit's date and time, "17 Nov, 15:26" (24 h) in the given zone. */
export function formatVisitAt(value: string, tz: string): string {
  const d = dayjs.utc(value);
  return d.isValid() ? d.tz(tz).format('D MMM, HH:mm') : value;
}

/** Seconds from `from` to `to` (ISO instants), or null when `from` is null / unreadable. */
export function secondsBetween(from: string | null | undefined, to: string): number | null {
  if (from === null || from === undefined || from === '') return null;
  const a = Date.parse(from);
  const b = Date.parse(to);
  if (Number.isNaN(a) || Number.isNaN(b)) return null;
  return Math.max(0, Math.floor((b - a) / 1000));
}

/**
 * Whether the gap is over the company's warning (CUSTOMER_HOURS `visit_gap_warning_hours`; null =
 * never flag). A first visit is never flagged.
 */
export function visitGapFlagged(
  seconds: number | null | undefined,
  warningHours: number | null,
): boolean {
  if (seconds === null || seconds === undefined || warningHours === null) return false;
  return seconds > warningHours * 3600;
}

/** Where a reading was taken: the phone's area label, the company site hint and the GPS point. */
export interface VisitPlace {
  place?: string | null | undefined;
  site?: string | null | undefined;
  lat?: number | null | undefined;
  lng?: number | null | undefined;
  accuracy?: number | null | undefined;
}

export interface WhereParts {
  /** "Mbezi Beach (at Yard)" / "at Yard" / "" (labels before the coordinates). */
  label: string;
  /** "-6.7924, 39.2083" */
  coords: string;
  /** " (±5 m)" or "" */
  accuracy: string;
  /** OpenStreetMap at the point. */
  mapUrl: string;
}

const present = (v: string | null | undefined): v is string => v != null && v.trim() !== '';

/** The parts of a Where line; null when there are no coordinates (no Where line at all). */
export function whereParts(p: VisitPlace): WhereParts | null {
  if (p.lat == null || p.lng == null) return null;
  const place = present(p.place) ? p.place.trim() : null;
  const site = present(p.site) ? p.site.trim() : null;
  const label =
    place !== null && site !== null
      ? `${place} (at ${site})`
      : place !== null
        ? place
        : site !== null
          ? `at ${site}`
          : '';
  const { lat, lng } = p;
  return {
    label,
    coords: `${lat.toFixed(4)}, ${lng.toFixed(4)}`,
    accuracy: p.accuracy == null ? '' : ` (±${String(Math.round(p.accuracy))} m)`,
    mapUrl: `https://www.openstreetmap.org/?mlat=${String(lat)}&mlon=${String(lng)}#map=17/${String(lat)}/${String(lng)}`,
  };
}

/** "Where: Mbezi Beach (at Yard) · -6.7924, 39.2083 (±5 m)", or null without coordinates. */
export function whereLine(p: VisitPlace): string | null {
  const w = whereParts(p);
  if (w === null) return null;
  return `Where: ${w.label === '' ? '' : `${w.label} · `}${w.coords}${w.accuracy}`;
}
