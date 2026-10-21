import type { Map as MapLibreMap } from 'maplibre-gl';
import { createContext, useContext } from 'react';

/** The loaded MapLibre map; provided by MapView to its children once the style has loaded. */
export const MapContext = createContext<MapLibreMap | null>(null);

export function useMapInstance(): MapLibreMap {
  const map = useContext(MapContext);
  if (map === null) throw new Error('Map children must be rendered inside <MapView>.');
  return map;
}
