import 'maplibre-gl/dist/maplibre-gl.css';
import './maplibreWorker';
import { Map as MapLibreMap, NavigationControl } from 'maplibre-gl';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { appConfig } from '../../config/env';
import { MapContext } from './MapContext';

/** [longitude, latitude] in WGS84. */
export type LngLat = readonly [number, number];

export interface MapViewProps {
  /** Initial center; later changes re-center the map without recreating it. */
  center: LngLat;
  zoom?: number;
  /** MapLibre style JSON URL; defaults to VITE_MAP_STYLE_URL. */
  styleUrl?: string;
  /** Accessible label for the map region. */
  ariaLabel: string;
  className?: string;
  /** Called once the style is loaded; add sources/layers here. */
  onReady?: (map: MapLibreMap) => void;
  /** Called just before the map is destroyed. */
  onDispose?: (map: MapLibreMap) => void;
  /** Declarative map children (GeoJsonLayer, FitBounds, click handlers); mounted after load. */
  children?: ReactNode;
}

/** Thin typed wrapper around a MapLibre GL map instance. Owns creation and disposal only. */
export function MapView({
  center,
  zoom = 10,
  styleUrl = appConfig.mapStyleUrl,
  ariaLabel,
  className,
  onReady,
  onDispose,
  children,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [loaded, setLoaded] = useState<MapLibreMap | null>(null);
  const callbacks = useRef({ onReady, onDispose });
  useEffect(() => {
    callbacks.current = { onReady, onDispose };
  }, [onReady, onDispose]);
  const [lng, lat] = center;

  useEffect(() => {
    const container = containerRef.current;
    if (container === null) return undefined;
    const map = new MapLibreMap({ container, style: styleUrl, center: [lng, lat], zoom });
    map.addControl(new NavigationControl(), 'top-right');
    mapRef.current = map;
    map.on('load', () => {
      callbacks.current.onReady?.(map);
      setLoaded(map);
    });
    return () => {
      setLoaded(null);
      callbacks.current.onDispose?.(map);
      map.remove();
      mapRef.current = null;
    };
    // Center/zoom changes are applied below without recreating the map.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [styleUrl]);

  useEffect(() => {
    mapRef.current?.jumpTo({ center: [lng, lat], zoom });
  }, [lng, lat, zoom]);

  return (
    <>
      <div
        ref={containerRef}
        role="region"
        aria-label={ariaLabel}
        className={className ?? 'h-96 w-full rounded'}
      />
      {loaded !== null && <MapContext.Provider value={loaded}>{children}</MapContext.Provider>}
    </>
  );
}
