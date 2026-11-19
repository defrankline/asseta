import { describe, expect, it } from 'vitest';
import {
  formatVisitAt,
  formatVisitGap,
  secondsBetween,
  visitGapFlagged,
  whereLine,
  whereParts,
} from './visitDisplay';

const MIN = 60;
const HOUR = 3600;
const DAY = 86400;

describe('time since last visit', () => {
  it('formats the gap in whole, truncated units', () => {
    expect(formatVisitGap(null)).toBe('First visit');
    expect(formatVisitGap(undefined)).toBe('First visit');
    expect(formatVisitGap(0)).toBe('0 min');
    expect(formatVisitGap(59)).toBe('0 min');
    expect(formatVisitGap(45 * MIN + 59)).toBe('45 min');
    expect(formatVisitGap(HOUR)).toBe('1 h');
    expect(formatVisitGap(5 * HOUR)).toBe('5 h');
    expect(formatVisitGap(5 * HOUR + 20 * MIN + 30)).toBe('5 h 20 min');
    expect(formatVisitGap(DAY - 1)).toBe('23 h 59 min');
    expect(formatVisitGap(DAY)).toBe('1 day');
    expect(formatVisitGap(DAY + 3 * HOUR + 59 * MIN)).toBe('1 day 3 h');
    expect(formatVisitGap(2 * DAY + 30 * MIN)).toBe('2 days');
    expect(formatVisitGap(10 * DAY + HOUR)).toBe('10 days 1 h');
  });

  it('dates a visit as "17 Nov, 15:26" in the display zone', () => {
    expect(formatVisitAt('2026-11-17T12:26:00Z', 'Africa/Dar_es_Salaam')).toBe('17 Nov, 15:26');
    expect(formatVisitAt('2026-11-17T12:26:00Z', 'UTC')).toBe('17 Nov, 12:26');
  });

  it('counts the gap from the last visit to the reading', () => {
    expect(secondsBetween(null, '2026-11-17T12:00:00Z')).toBeNull();
    expect(secondsBetween('2026-11-16T09:00:00Z', '2026-11-17T12:00:00Z')).toBe(DAY + 3 * HOUR);
    expect(secondsBetween('2026-11-18T09:00:00Z', '2026-11-17T12:00:00Z')).toBe(0);
  });

  it('flags a gap over the company warning only', () => {
    expect(visitGapFlagged(24 * HOUR + 1, 24)).toBe(true);
    expect(visitGapFlagged(24 * HOUR, 24)).toBe(false);
    expect(visitGapFlagged(null, 24)).toBe(false);
    expect(visitGapFlagged(10 * DAY, null)).toBe(false);
  });
});

describe('where line', () => {
  const at = { lat: -6.79241, lng: 39.20834, accuracy: 4.6 };
  it('shows the place, the site, the point and the accuracy, leaving out what is missing', () => {
    expect(whereLine({ ...at, place: 'Mbezi Beach, Kinondoni', site: 'Yard' })).toBe(
      'Where: Mbezi Beach, Kinondoni (at Yard) · -6.7924, 39.2083 (±5 m)',
    );
    expect(whereLine({ ...at, place: 'Mbezi Beach' })).toBe(
      'Where: Mbezi Beach · -6.7924, 39.2083 (±5 m)',
    );
    expect(whereLine({ ...at, place: null, site: 'Yard' })).toBe(
      'Where: at Yard · -6.7924, 39.2083 (±5 m)',
    );
    expect(whereLine(at)).toBe('Where: -6.7924, 39.2083 (±5 m)');
    expect(whereLine({ lat: -6.7924, lng: 39.2083, accuracy: null })).toBe(
      'Where: -6.7924, 39.2083',
    );
    expect(whereLine({ lat: null, lng: 39.2, place: 'Mbezi' })).toBeNull();
    expect(whereLine({})).toBeNull();
  });

  it('links the point to OpenStreetMap', () => {
    expect(whereParts({ lat: -6.7924, lng: 39.2083 })?.mapUrl).toBe(
      'https://www.openstreetmap.org/?mlat=-6.7924&mlon=39.2083#map=17/-6.7924/39.2083',
    );
  });
});
