import { LngLatBounds } from 'maplibre-gl';
import { useEffect } from 'react';
import { useMapInstance } from './MapContext';

interface FitBoundsProps {
  /** Positions `[lon, lat]` to keep in view. */
  positions: readonly (readonly [number, number])[];
  /** Re-fit only when this key changes (e.g. a new history query), not on every data refresh. */
  fitKey: string;
  maxZoom?: number;
}

/** Fits the map to the given positions once per `fitKey`. */
export function FitBounds({ positions, fitKey, maxZoom = 15 }: FitBoundsProps) {
  const map = useMapInstance();
  const first = positions[0];
  const empty = first === undefined;
  useEffect(() => {
    if (first === undefined) return;
    const bounds = new LngLatBounds([first[0], first[1]], [first[0], first[1]]);
    for (const [lon, lat] of positions) bounds.extend([lon, lat]);
    map.fitBounds(bounds, { padding: 48, maxZoom, duration: 0 });
    // Positions intentionally excluded: refits are driven by fitKey only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, fitKey, empty, maxZoom]);
  return null;
}
