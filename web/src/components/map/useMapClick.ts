import type { MapMouseEvent } from 'maplibre-gl';
import { useEffect, useRef } from 'react';
import { useMapInstance } from './MapContext';

/** Invokes `handler([lon, lat])` for every click on the map background while `enabled`. */
export function useMapClick(handler: (lngLat: [number, number]) => void, enabled = true): void {
  const map = useMapInstance();
  const saved = useRef(handler);
  useEffect(() => {
    saved.current = handler;
  }, [handler]);
  useEffect(() => {
    if (!enabled) return undefined;
    const onClick = (e: MapMouseEvent) => {
      saved.current([e.lngLat.lng, e.lngLat.lat]);
    };
    map.on('click', onClick);
    const canvas = map.getCanvas();
    const previous = canvas.style.cursor;
    canvas.style.cursor = 'crosshair';
    return () => {
      map.off('click', onClick);
      canvas.style.cursor = previous;
    };
  }, [map, enabled]);
}
