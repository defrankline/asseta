import { Box, Typography } from '@mui/material';
import type { AddLayerObject } from 'maplibre-gl';
import { useMemo } from 'react';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { GeoJsonLayer } from '../../../components/map/GeoJsonLayer';
import { featureCollection, pointFeature } from '../../../components/map/geo';
import { MapView } from '../../../components/map/MapView';
import { humanize } from '../../../utils/text';

/** `[lon, lat]` when the evidence carries numeric `lat`/`lon`, else null. */
function evidencePosition(evidence: Record<string, unknown>): [number, number] | null {
  const { lat, lon } = evidence;
  return typeof lat === 'number' && typeof lon === 'number' ? [lon, lat] : null;
}

function display(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

const LAYERS: AddLayerObject[] = [
  {
    id: 'alert-evidence-point',
    type: 'circle',
    source: 'alert-evidence',
    paint: {
      'circle-radius': 8,
      'circle-color': '#dc2626',
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 2,
    },
  },
];

/** Alert evidence as labelled key-values plus a mini map when it holds a position. */
export function EvidenceView({ evidence }: { evidence: Record<string, unknown> }) {
  const position = evidencePosition(evidence);
  const data = useMemo(
    () => featureCollection(position === null ? [] : [pointFeature(position)]),
    [position],
  );
  const items = Object.entries(evidence).map(([key, value]) => ({
    label: humanize(key),
    value: <span className="font-mono">{display(value)}</span>,
  }));
  return (
    <Box className="flex flex-col gap-3">
      <Typography variant="subtitle2" component="h3">
        Evidence
      </Typography>
      {items.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No evidence recorded.
        </Typography>
      ) : (
        <KeyValueGrid columns={2} items={items} />
      )}
      {position !== null && (
        <MapView
          center={position}
          zoom={14}
          ariaLabel="Alert evidence location"
          className="h-56 w-full rounded"
        >
          <GeoJsonLayer id="alert-evidence" data={data} layers={LAYERS} />
        </MapView>
      )}
    </Box>
  );
}
