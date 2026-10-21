import {
  circleFeature,
  featureCollection,
  lineFeature,
  pointFeature,
  type LonLat,
} from '../map/geo';

export interface TrackerPosition {
  latitude: number;
  longitude: number;
  accuracyM: number | null;
}

const positive = (v: number | null): v is number => v !== null && v > 0;

/** Build the map features: phone fix (+accuracy), tracker point (+accuracy) and allowed-distance ring. */
export function captureLocationFeatures(
  phone: LonLat,
  accuracyM: number | null,
  allowedM: number | null,
  tracker: TrackerPosition | null,
) {
  const t: LonLat | null = tracker === null ? null : [tracker.longitude, tracker.latitude];
  return featureCollection([
    ...(positive(accuracyM) ? [circleFeature(phone, accuracyM, { role: 'phone-accuracy' })] : []),
    ...(t !== null && tracker !== null && positive(tracker.accuracyM)
      ? [circleFeature(t, tracker.accuracyM, { role: 'tracker-accuracy' })]
      : []),
    ...(positive(allowedM) ? [circleFeature(phone, allowedM, { role: 'allowed' })] : []),
    ...(t !== null ? [lineFeature([phone, t], { role: 'link' })] : []),
    pointFeature(phone, { role: 'phone' }),
    ...(t !== null ? [pointFeature(t, { role: 'tracker' })] : []),
  ]);
}
