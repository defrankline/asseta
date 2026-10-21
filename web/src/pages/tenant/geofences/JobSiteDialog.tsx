import { Alert, Typography } from '@mui/material';
import { getIn } from 'formik';
import type { AddLayerObject } from 'maplibre-gl';
import { useState } from 'react';
import { mixed, object, string } from 'yup';
import { geofenceService } from '../../../api/services/geofenceService';
import type { JobSiteDto, JobSiteIn } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { GeoJsonLayer } from '../../../components/map/GeoJsonLayer';
import { featureCollection, pointFeature, type LonLat } from '../../../components/map/geo';
import { MapView } from '../../../components/map/MapView';
import { useMapClick } from '../../../components/map/useMapClick';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { DEFAULT_MAP_CENTER } from '../shared/display';

interface JobSiteValues {
  code: string;
  name: string;
  address: string;
  center: LonLat | null;
}

const schema = object({
  code: string().trim().required('Code is required').max(32, 'At most 32 characters'),
  name: string().trim().required('Name is required').max(200, 'At most 200 characters'),
  address: string().trim().max(300, 'At most 300 characters').default(''),
  center: mixed<LonLat>()
    .nullable()
    .defined()
    .test('center', 'Click the map to set the site center', (v) => v !== null),
});

const LAYERS: AddLayerObject[] = [
  {
    id: 'job-site-center-point',
    type: 'circle',
    source: 'job-site-center',
    paint: {
      'circle-radius': 8,
      'circle-color': '#2563eb',
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 2,
    },
  },
];

function CenterPicker({ center, onPick }: { center: LonLat | null; onPick: (p: LonLat) => void }) {
  useMapClick(onPick);
  return (
    <GeoJsonLayer
      id="job-site-center"
      data={featureCollection(center === null ? [] : [pointFeature(center)])}
      layers={LAYERS}
    />
  );
}

function LocationMap({ center, onPick }: { center: LonLat | null; onPick: (p: LonLat) => void }) {
  // Freeze the initial view; picking a point must not recenter / re-zoom the map.
  const [initial] = useState<LonLat>(
    () => center ?? [DEFAULT_MAP_CENTER[0], DEFAULT_MAP_CENTER[1]],
  );
  return (
    <MapView
      center={initial}
      zoom={12}
      ariaLabel="Job site location map"
      className="h-72 w-full rounded"
    >
      <CenterPicker center={center} onPick={onPick} />
    </MapView>
  );
}

const fmt = (c: LonLat | null) =>
  c === null ? 'Not set' : `${c[1].toFixed(6)}, ${c[0].toFixed(6)} (lat, lon)`;

/** Details → Location (map click) → Review. Mount only while open. */
export function JobSiteDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (site: JobSiteDto) => void;
}) {
  const keyFor = useIdempotencyKey();
  const [initialValues] = useState<JobSiteValues>({
    code: '',
    name: '',
    address: '',
    center: null,
  });
  const steps: FormStep<JobSiteValues>[] = [
    {
      label: 'Details',
      fields: ['code', 'name', 'address'],
      render: () => (
        <>
          <FormikTextField name="code" label="Code" required />
          <FormikTextField name="name" label="Name" required />
          <FormikTextField name="address" label="Address" />
        </>
      ),
    },
    {
      label: 'Location',
      fields: ['center'],
      render: (formik) => {
        const err: unknown = getIn(formik.errors, 'center');
        return (
          <>
            <Typography variant="body2" color="text.secondary">
              Click the map to place the site center.
            </Typography>
            <LocationMap
              center={formik.values.center}
              onPick={(p) => {
                void formik.setFieldValue('center', p);
              }}
            />
            <Typography variant="body2">Center: {fmt(formik.values.center)}</Typography>
            {getIn(formik.touched, 'center') === true && typeof err === 'string' && (
              <Alert severity="error">{err}</Alert>
            )}
          </>
        );
      },
    },
  ];
  return (
    <StepperFormDialog<JobSiteValues>
      open
      title="New job site"
      steps={steps}
      initialValues={initialValues}
      validationSchema={schema}
      submitLabel="Create job site"
      onClose={onClose}
      renderReview={(v) => (
        <KeyValueGrid
          columns={2}
          items={[
            { label: 'Code', value: v.code },
            { label: 'Name', value: v.name },
            { label: 'Address', value: v.address === '' ? '—' : v.address },
            { label: 'Center', value: fmt(v.center) },
          ]}
        />
      )}
      onSubmit={async (v) => {
        if (v.center === null) return;
        const address = v.address.trim();
        const body: JobSiteIn = {
          code: v.code.trim(),
          name: v.name.trim(),
          address: address === '' ? null : address,
          center: { type: 'Point', coordinates: [v.center[0], v.center[1]] },
        };
        onCreated(await geofenceService.createJobSite(body, keyFor(body)));
      }}
    />
  );
}
