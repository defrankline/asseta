import type { Feature } from 'geojson';
import type { AddLayerObject } from 'maplibre-gl';
import { useMemo } from 'react';
import type { GeofenceDto, JobSiteDto } from '../../../api/types';
import { FitBounds } from '../../../components/map/FitBounds';
import { GeoJsonLayer } from '../../../components/map/GeoJsonLayer';
import {
  asGeoJson,
  collectPositions,
  featureCollection,
  pointFeature,
} from '../../../components/map/geo';
import { MapView } from '../../../components/map/MapView';
import { DEFAULT_MAP_CENTER, GEOFENCE_KIND_COLORS } from '../shared/display';

interface GeofencesMapProps {
  geofences: readonly GeofenceDto[];
  sites: readonly JobSiteDto[];
  selectedId: string | null;
  onSelect: (geofenceId: string) => void;
}

/** Features of a geofence's server-computed `area_geojson`, tagged for styling. */
function areaFeatures(g: GeofenceDto, selected: boolean): Feature[] {
  const geo = asGeoJson(g.area_geojson);
  if (geo === null) return [];
  const props = { id: g.id, color: GEOFENCE_KIND_COLORS[g.kind], selected, active: g.is_active };
  const features = geo.type === 'FeatureCollection' ? geo.features : [geo];
  return features.map((f) => ({
    type: 'Feature',
    geometry: f.geometry,
    properties: { ...f.properties, ...props },
  }));
}

const AREA_LAYERS: AddLayerObject[] = [
  {
    id: 'geofence-areas-fill',
    type: 'fill',
    source: 'geofence-areas',
    paint: {
      'fill-color': ['get', 'color'],
      'fill-opacity': ['case', ['get', 'selected'], 0.35, ['get', 'active'], 0.15, 0.05],
    },
  },
  {
    id: 'geofence-areas-line',
    type: 'line',
    source: 'geofence-areas',
    paint: {
      'line-color': ['get', 'color'],
      'line-width': ['case', ['get', 'selected'], 3, 1.5],
    },
  },
];

const SITE_LAYERS: AddLayerObject[] = [
  {
    id: 'job-sites-point',
    type: 'circle',
    source: 'job-sites',
    paint: {
      'circle-radius': 6,
      'circle-color': '#111827',
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 2,
    },
  },
];

/** Overview of all geofence areas (coloured by kind) and job site centers. */
export function GeofencesMap({ geofences, sites, selectedId, onSelect }: GeofencesMapProps) {
  const areas = useMemo(
    () => featureCollection(geofences.flatMap((g) => areaFeatures(g, g.id === selectedId))),
    [geofences, selectedId],
  );
  const sitePoints = useMemo(
    () =>
      featureCollection(
        sites.map((s) =>
          pointFeature([s.center.coordinates[0], s.center.coordinates[1]], { id: s.id }),
        ),
      ),
    [sites],
  );
  const selected = geofences.find((g) => g.id === selectedId);
  const fitPositions = useMemo(
    () =>
      selected !== undefined
        ? collectPositions(selected.area_geojson)
        : [...collectPositions(areas), ...collectPositions(sitePoints)],
    [selected, areas, sitePoints],
  );
  return (
    <MapView
      center={DEFAULT_MAP_CENTER}
      zoom={11}
      ariaLabel="Sites and geofences map"
      className="h-[28rem] w-full rounded"
    >
      <GeoJsonLayer
        id="geofence-areas"
        data={areas}
        layers={AREA_LAYERS}
        clickLayerId="geofence-areas-fill"
        onFeatureClick={(p) => {
          if (typeof p.id === 'string') onSelect(p.id);
        }}
      />
      <GeoJsonLayer id="job-sites" data={sitePoints} layers={SITE_LAYERS} />
      <FitBounds positions={fitPositions} fitKey={selectedId ?? 'all'} />
    </MapView>
  );
}
