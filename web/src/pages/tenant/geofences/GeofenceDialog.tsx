import { FormControlLabel, Radio, RadioGroup } from '@mui/material';
import { getIn } from 'formik';
import { useCallback, useState } from 'react';
import { geofenceService } from '../../../api/services/geofenceService';
import { machineService } from '../../../api/services/machineService';
import type { GeofenceDto, JobSiteDto } from '../../../api/types';
import { AsyncMultiAutocomplete } from '../../../components/data/AsyncMultiAutocomplete';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StaleVersionAlert } from '../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../components/lifecycle/useStaleVersion';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import type { LonLat } from '../../../components/map/geo';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import {
  DEFAULT_MAP_CENTER,
  GEOFENCE_KIND_OPTIONS,
  labelOf,
  machineLabel,
} from '../shared/display';
import {
  EMPTY_GEOFENCE,
  geofenceSchema,
  geofenceToValues,
  toGeofencePayload,
  type GeofenceFormValues,
  type MachineOption,
} from './geofenceForm';
import { FormikJobSitePicker } from '../shared/lookupPickers';
import { jobSiteLabel } from '../shared/lookups';
import { GeofenceShapeStep } from './GeofenceShapeStep';

interface GeofenceDialogProps {
  /** Existing geofence to edit; omit to create. */
  geofence?: GeofenceDto;
  sites: readonly JobSiteDto[];
  machineLabels: ReadonlyMap<string, string>;
  onClose: () => void;
  onSaved: (geofence: GeofenceDto) => void;
  /** Edit only: the server reported STALE_VERSION and the user chose Reload. */
  onReloadRequested?: () => void;
}

/** Details → Shape (draw) → Applies to → Review. Mount only while open. */
export function GeofenceDialog({
  geofence,
  sites,
  machineLabels,
  onClose,
  onSaved,
  onReloadRequested,
}: GeofenceDialogProps) {
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  const [initialValues] = useState<GeofenceFormValues>(() =>
    geofence === undefined ? EMPTY_GEOFENCE : geofenceToValues(geofence, machineLabels),
  );
  const [site, setSite] = useState<JobSiteDto | null>(null);
  /** Edit form: the page already holds the job sites (for the map), so resolve from them. */
  const resolveSite = useCallback(
    (id: string) => Promise.resolve(sites.find((s) => s.id === id) ?? null),
    [sites],
  );
  const fetchMachines = useCallback(
    async (q: string, signal: AbortSignal): Promise<MachineOption[]> =>
      (await machineService.list({ page: 1, page_size: 20, q }, signal)).items.map((m) => ({
        id: m.id,
        label: machineLabel(m),
      })),
    [],
  );
  const centerFor = (siteId: string): LonLat => {
    if (site !== null && site.id === siteId) {
      return [site.center.coordinates[0], site.center.coordinates[1]];
    }
    return [DEFAULT_MAP_CENTER[0], DEFAULT_MAP_CENTER[1]];
  };

  const steps: FormStep<GeofenceFormValues>[] = [
    {
      label: 'Details',
      fields: ['name', 'kind', 'job_site_id'],
      render: () => (
        <>
          <FormikTextField name="name" label="Name" required />
          <FormikSelectField name="kind" label="Kind" options={GEOFENCE_KIND_OPTIONS} required />
          <FormikJobSitePicker
            name="job_site_id"
            label="Job site (optional)"
            resolveOption={resolveSite}
            onOptionChange={setSite}
          />
        </>
      ),
    },
    {
      label: 'Shape',
      fields: ['vertices', 'corridor_width_m'],
      render: (formik) => (
        <GeofenceShapeStep formik={formik} fallbackCenter={centerFor(formik.values.job_site_id)} />
      ),
    },
    {
      label: 'Applies to',
      fields: ['machines'],
      render: (formik) => {
        const err: unknown = getIn(formik.errors, 'machines');
        return (
          <>
            <RadioGroup
              value={formik.values.applies_to}
              onChange={(e) => {
                void formik.setFieldValue('applies_to', e.target.value);
              }}
              aria-label="Applies to"
            >
              <FormControlLabel value="ALL" control={<Radio />} label="All machines" />
              <FormControlLabel value="SELECTED" control={<Radio />} label="Selected machines" />
            </RadioGroup>
            {formik.values.applies_to === 'SELECTED' && (
              <AsyncMultiAutocomplete<MachineOption>
                label="Machines"
                value={formik.values.machines}
                onChange={(next) => {
                  void formik.setFieldValue('machines', next);
                }}
                fetchOptions={fetchMachines}
                getOptionLabel={(m) => m.label}
                isOptionEqualToValue={(a, b) => a.id === b.id}
                error={
                  getIn(formik.touched, 'machines') === true && typeof err === 'string'
                    ? err
                    : undefined
                }
              />
            )}
          </>
        );
      },
    },
  ];

  return (
    <StepperFormDialog<GeofenceFormValues>
      open
      title={geofence === undefined ? 'New geofence' : `Edit geofence · ${geofence.name}`}
      steps={steps}
      initialValues={initialValues}
      validationSchema={geofenceSchema}
      submitLabel={geofence === undefined ? 'Create geofence' : 'Save geofence'}
      onClose={onClose}
      renderReview={(v) => (
        <>
          {stale && (
            <StaleVersionAlert
              onReload={() => {
                onReloadRequested?.();
                onClose();
              }}
            />
          )}
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Name', value: v.name },
              { label: 'Kind', value: labelOf(GEOFENCE_KIND_OPTIONS, v.kind) },
              {
                label: 'Job site',
                value:
                  v.job_site_id === ''
                    ? 'None'
                    : site?.id === v.job_site_id
                      ? jobSiteLabel(site)
                      : v.job_site_id,
              },
              {
                label: 'Shape',
                value:
                  v.shape === 'POLYGON'
                    ? `Polygon · ${String(v.vertices.length)} vertices (closed ring)`
                    : `Corridor · ${String(v.vertices.length)} points · ${v.corridor_width_m} m wide`,
              },
              {
                label: 'Applies to',
                value:
                  v.applies_to === 'ALL'
                    ? 'All machines'
                    : v.machines.map((m) => m.label).join(', '),
              },
              { label: 'Area', value: 'Computed by the server after saving' },
            ]}
          />
        </>
      )}
      onSubmit={async (values) => {
        if (geofence === undefined) {
          const body = toGeofencePayload(values);
          onSaved(await geofenceService.create(body, keyFor(body)));
          return;
        }
        // Optimistic concurrency: send the version that was read.
        const body = { ...toGeofencePayload(values), version: geofence.version };
        onSaved(await guard(() => geofenceService.update(geofence.id, body, keyFor(body))));
      }}
    />
  );
}
