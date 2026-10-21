import { Alert, Box, Button, FormControlLabel, Radio, RadioGroup, Typography } from '@mui/material';
import { getIn, type FormikProps } from 'formik';
import { useState } from 'react';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { canComplete } from '../../../components/map/drawing';
import { DrawPolygonControl } from '../../../components/map/DrawPolygonControl';
import type { LonLat } from '../../../components/map/geo';
import { MapView } from '../../../components/map/MapView';
import { GEOFENCE_KIND_COLORS } from '../shared/display';
import type { GeofenceFormValues } from './geofenceForm';

interface GeofenceShapeStepProps {
  formik: FormikProps<GeofenceFormValues>;
  /** Initial map center when nothing is drawn yet (e.g. the job site center). */
  fallbackCenter: LonLat;
}

/** Shape choice and click-to-draw: polygon vertices (undo / close ring) or corridor polyline. */
export function GeofenceShapeStep({ formik, fallbackCenter }: GeofenceShapeStepProps) {
  const { values, setFieldValue } = formik;
  const polygon = values.shape === 'POLYGON';
  const set = (vertices: LonLat[], closed: boolean) => {
    void setFieldValue('vertices', vertices);
    void setFieldValue('closed', closed);
  };
  const errorRaw: unknown = getIn(formik.errors, 'vertices');
  const error =
    getIn(formik.touched, 'vertices') === true && typeof errorRaw === 'string' ? errorRaw : null;
  // Freeze the initial view; later clicks must not recenter / re-zoom the map.
  const [center] = useState<LonLat>(() => values.vertices[0] ?? fallbackCenter);
  const status = polygon
    ? `${String(values.vertices.length)} vertices · ${values.closed ? 'ring closed' : 'ring open'}`
    : `${String(values.vertices.length)} points on the centre line`;

  return (
    <>
      <RadioGroup
        row
        value={values.shape}
        onChange={(e) => {
          void setFieldValue('shape', e.target.value);
          set([], false);
        }}
        aria-label="Shape"
      >
        <FormControlLabel value="POLYGON" control={<Radio />} label="Polygon" />
        <FormControlLabel value="CORRIDOR" control={<Radio />} label="Corridor (route + width)" />
      </RadioGroup>
      <Typography variant="body2" color="text.secondary">
        {polygon
          ? 'Click the map to add vertices, then close the ring.'
          : 'Click the map to trace the corridor centre line, then set its width.'}
      </Typography>
      <MapView
        center={center}
        zoom={14}
        ariaLabel="Geofence drawing map"
        className="h-72 w-full rounded"
      >
        <DrawPolygonControl
          mode={polygon ? 'polygon' : 'line'}
          vertices={values.vertices}
          closed={values.closed}
          color={GEOFENCE_KIND_COLORS[values.kind]}
          onAddVertex={(p) => {
            set([...values.vertices, p], false);
          }}
        />
      </MapView>
      <Box className="flex flex-wrap items-center gap-2">
        <Typography variant="body2" aria-live="polite">
          {status}
        </Typography>
        <Button
          size="small"
          disabled={values.vertices.length === 0}
          onClick={() => {
            set(values.closed ? values.vertices : values.vertices.slice(0, -1), false);
          }}
        >
          {values.closed ? 'Reopen ring' : 'Undo'}
        </Button>
        <Button
          size="small"
          disabled={values.vertices.length === 0}
          onClick={() => {
            set([], false);
          }}
        >
          Clear
        </Button>
        {polygon && (
          <Button
            size="small"
            variant="outlined"
            disabled={values.closed || !canComplete('polygon', values.vertices)}
            onClick={() => {
              set(values.vertices, true);
            }}
          >
            Close ring
          </Button>
        )}
      </Box>
      {error !== null && <Alert severity="error">{error}</Alert>}
      {!polygon && (
        <FormikTextField
          name="corridor_width_m"
          label="Corridor width (m)"
          required
          slotProps={{ htmlInput: { inputMode: 'decimal' } }}
          helperText="Total width of the corridor around the centre line."
        />
      )}
    </>
  );
}
