import type { GeoJSONSource, AddLayerObject } from 'maplibre-gl';
import type { GeoJSON } from 'geojson';
import { useEffect, useRef } from 'react';
import { useMapInstance } from './MapContext';

interface GeoJsonLayerProps {
  /** Source id; layers must reference it as `source`. */
  id: string;
  data: GeoJSON;
  /** Layers drawn from this source, bottom to top. */
  layers: readonly AddLayerObject[];
  /** Called with the feature properties when a feature of `clickLayerId` is clicked. */
  onFeatureClick?: (properties: Record<string, unknown>) => void;
  /** Layer id that receives clicks (defaults to the top layer). */
  clickLayerId?: string;
}

function safely(fn: () => void): void {
  try {
    fn();
  } catch {
    // The map (or its style) may already be torn down.
  }
}

/** Declarative GeoJSON source + layers on the surrounding MapView; data updates in place. */
export function GeoJsonLayer({
  id,
  data,
  layers,
  onFeatureClick,
  clickLayerId,
}: GeoJsonLayerProps) {
  const map = useMapInstance();
  const latest = useRef({ data, onFeatureClick });
  useEffect(() => {
    latest.current = { data, onFeatureClick };
  }, [data, onFeatureClick]);
  const layerKey = JSON.stringify(layers);
  const clickLayer = clickLayerId ?? layers[layers.length - 1]?.id;

  useEffect(() => {
    const defs = JSON.parse(layerKey) as AddLayerObject[];
    map.addSource(id, { type: 'geojson', data: latest.current.data });
    for (const layer of defs) map.addLayer(layer);
    const onClick = (e: { features?: { properties: Record<string, unknown> }[] }) => {
      const props = e.features?.[0]?.properties;
      if (props !== undefined) latest.current.onFeatureClick?.(props);
    };
    if (clickLayer !== undefined) map.on('click', clickLayer, onClick);
    return () => {
      if (clickLayer !== undefined) safely(() => map.off('click', clickLayer, onClick));
      for (const layer of [...defs].reverse()) {
        safely(() => {
          if (map.getLayer(layer.id) !== undefined) map.removeLayer(layer.id);
        });
      }
      safely(() => {
        if (map.getSource(id) !== undefined) map.removeSource(id);
      });
    };
  }, [map, id, layerKey, clickLayer]);

  useEffect(() => {
    const source = map.getSource<GeoJSONSource>(id);
    if (source !== undefined) void source.setData(data);
  }, [map, id, data]);

  return null;
}
