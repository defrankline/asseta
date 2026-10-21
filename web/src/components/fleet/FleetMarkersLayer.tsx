import type { AddLayerObject } from 'maplibre-gl';
import { useMemo } from 'react';
import type { MachineMapDto } from '../../api/types';
import { GeoJsonLayer } from '../map/GeoJsonLayer';
import { featureCollection, pointFeature } from '../map/geo';
import { markerStyle } from './connectivity';

interface FleetMarkersLayerProps {
  machines: readonly MachineMapDto[];
  selectedId: string | null;
  onSelect: (machineId: string) => void;
}

const SOURCE = 'fleet-machines';

const LAYERS: AddLayerObject[] = [
  {
    id: `${SOURCE}-selected`,
    type: 'circle',
    source: SOURCE,
    filter: ['==', ['get', 'selected'], true],
    paint: { 'circle-radius': 14, 'circle-color': '#111827', 'circle-opacity': 0.15 },
  },
  {
    id: `${SOURCE}-marker`,
    type: 'circle',
    source: SOURCE,
    paint: {
      'circle-radius': ['case', ['get', 'live'], 8, 7],
      'circle-color': ['get', 'color'],
      'circle-opacity': ['get', 'fillOpacity'],
      'circle-stroke-color': ['get', 'color'],
      'circle-stroke-width': ['case', ['get', 'hollow'], 3, 2],
      'circle-stroke-opacity': ['get', 'opacity'],
    },
  },
];

/** One circle per machine with a position, styled by connectivity (hollow = last known). */
export function FleetMarkersLayer({ machines, selectedId, onSelect }: FleetMarkersLayerProps) {
  const data = useMemo(
    () =>
      featureCollection(
        machines.flatMap((m) =>
          m.longitude === null || m.latitude === null
            ? []
            : [
                pointFeature([m.longitude, m.latitude], {
                  machineId: m.machine_id,
                  selected: m.machine_id === selectedId,
                  ...markerStyle(m.connectivity, m.is_live),
                }),
              ],
        ),
      ),
    [machines, selectedId],
  );
  return (
    <GeoJsonLayer
      id={SOURCE}
      data={data}
      layers={LAYERS}
      clickLayerId={`${SOURCE}-marker`}
      onFeatureClick={(p) => {
        if (typeof p.machineId === 'string') onSelect(p.machineId);
      }}
    />
  );
}
