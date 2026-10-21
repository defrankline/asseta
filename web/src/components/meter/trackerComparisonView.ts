/** Typed reading of a capture's `tracker_comparison` evidence (free-form JSON from the API). */

export type TrackerComparisonView =
  | { kind: 'absent' }
  | { kind: 'not_compared'; reason: string | null }
  | {
      kind: 'compared';
      distanceM: number | null;
      allowedM: number | null;
      trackerTime: string | null;
      timeOffsetS: number | null;
      /** Tracker position used for the comparison (null when not reported). */
      trackerLatitude: number | null;
      trackerLongitude: number | null;
      trackerAccuracyM: number | null;
    };

const num = (v: unknown): number | null => (typeof v === 'number' ? v : null);
const str = (v: unknown): string | null => (typeof v === 'string' ? v : null);

export function readTrackerComparison(
  value: Record<string, unknown> | null,
): TrackerComparisonView {
  if (value === null) return { kind: 'absent' };
  if (value.compared !== true) return { kind: 'not_compared', reason: str(value.reason) };
  return {
    kind: 'compared',
    distanceM: num(value.distance_m),
    allowedM: num(value.allowed_m),
    trackerTime: str(value.tracker_time),
    timeOffsetS: num(value.time_offset_s),
    trackerLatitude: num(value.tracker_latitude),
    trackerLongitude: num(value.tracker_longitude),
    trackerAccuracyM: num(value.tracker_accuracy_m),
  };
}

/** True when the phone fix lay outside the allowed distance (null when unknown). */
export function isOutsideTolerance(view: TrackerComparisonView): boolean | null {
  if (view.kind !== 'compared' || view.distanceM === null || view.allowedM === null) return null;
  return view.distanceM > view.allowedM;
}
