import { Alert, Box, MenuItem, TextField, Typography } from '@mui/material';
import { getIn, type FormikProps } from 'formik';
import { useMemo, useState } from 'react';
import { policyService } from '../../../api/services/policyService';
import type { JobSiteDto, MachineDto, PolicyVersionDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { DateTimeField } from '../../../components/forms/DateTimeField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatInstantIn } from '../../../utils/time';
import { machineLabel } from '../shared/display';
import { MachinePicker } from '../shared/MachinePicker';
import { OverrideFieldInput } from './OverrideFieldInput';
import { withPolicyErrorCode } from './policyErrors';
import {
  allowedFields,
  formatPolicyValue,
  TRACKING_FIELDS,
  type OverrideScope,
} from './policyFields';
import {
  initialPolicyValues,
  policyFormSchema,
  toPolicyPayload,
  type PolicyFormValues,
} from './policyForm';

interface PolicyOverrideDialogProps {
  initialScope: OverrideScope;
  initialMachine: MachineDto | null;
  initialSiteId: string;
  /** Current effective values, used to prefill inputs. */
  current: Record<string, unknown> | null;
  sites: readonly JobSiteDto[] | null;
  timeZone: string;
  onClose: () => void;
  onCreated: (version: PolicyVersionDto) => void;
}

const SCOPE_LABELS: Readonly<Record<OverrideScope, string>> = {
  TENANT: 'Tenant default (all fields)',
  MACHINE: 'Machine override',
  SITE: 'Site override',
};

function ScopeStep({
  formik,
  sites,
  timeZone,
}: {
  formik: FormikProps<PolicyFormValues>;
  sites: readonly JobSiteDto[] | null;
  timeZone: string;
}) {
  const { values, setFieldValue, touched, errors } = formik;
  const err = (path: string): string | undefined => {
    const e: unknown = getIn(errors, path);
    return getIn(touched, path) === true && typeof e === 'string' ? e : undefined;
  };
  return (
    <>
      <TextField
        select
        label="Scope"
        value={values.scope}
        onChange={(e) => {
          const scope = e.target.value as OverrideScope;
          void setFieldValue('scope', scope);
          // Reset toggles so fields from another scope never leak into the payload.
          for (const def of TRACKING_FIELDS) {
            void setFieldValue(`overrides.${def.key}.enabled`, false, false);
          }
        }}
        fullWidth
      >
        {(['TENANT', 'MACHINE', 'SITE'] as const)
          .filter((s) => s !== 'SITE' || sites !== null)
          .map((s) => (
            <MenuItem key={s} value={s}>
              {SCOPE_LABELS[s]}
            </MenuItem>
          ))}
      </TextField>
      {values.scope === 'MACHINE' && (
        <MachinePicker
          value={values.machine}
          onChange={(m) => {
            void setFieldValue('machine', m);
          }}
          required
          error={err('machine')}
        />
      )}
      {values.scope === 'SITE' && (
        <TextField
          select
          label="Job site"
          required
          value={values.site_id}
          onChange={(e) => {
            void setFieldValue('site_id', e.target.value);
          }}
          error={err('site_id') !== undefined}
          helperText={err('site_id')}
          fullWidth
        >
          {(sites ?? []).map((s) => (
            <MenuItem key={s.id} value={s.id}>
              {s.code} · {s.name}
            </MenuItem>
          ))}
        </TextField>
      )}
      <DateTimeField
        label="Effective from (empty = now)"
        value={values.effective_from === '' ? null : values.effective_from}
        onChange={(v) => {
          void setFieldValue('effective_from', v ?? '');
        }}
        timezone={timeZone}
        helperText="Changes cannot be backdated."
      />
      <FormikTextField name="reason" label="Reason" required multiline minRows={2} />
    </>
  );
}

function ValuesStep({ formik }: { formik: FormikProps<PolicyFormValues> }) {
  const fields = allowedFields(formik.values.scope);
  const groupError: unknown = formik.errors.overrides;
  return (
    <>
      <Alert severity="info">
        {formik.values.scope === 'TENANT'
          ? 'Tenant defaults may set every field.'
          : `Only these fields may be overridden for a ${formik.values.scope.toLowerCase()}.`}
      </Alert>
      {typeof groupError === 'string' && <Alert severity="error">{groupError}</Alert>}
      <Box className="flex flex-col gap-2">
        {fields.map((def) => (
          <OverrideFieldInput key={def.key} def={def} />
        ))}
      </Box>
    </>
  );
}

/** Scope + reason → allowed field values → Review. Mount only while open. */
export function PolicyOverrideDialog(props: PolicyOverrideDialogProps) {
  const { sites, timeZone, onClose, onCreated } = props;
  const keyFor = useIdempotencyKey();
  const [initialValues] = useState(() =>
    initialPolicyValues(
      props.initialScope,
      props.current,
      props.initialMachine,
      props.initialSiteId,
    ),
  );
  const siteName = useMemo(
    () => new Map((sites ?? []).map((s) => [s.id, `${s.code} · ${s.name}`])),
    [sites],
  );

  const steps: FormStep<PolicyFormValues>[] = [
    {
      label: 'Scope',
      fields: ['scope', 'machine', 'site_id', 'reason'],
      render: (formik) => <ScopeStep formik={formik} sites={sites} timeZone={timeZone} />,
    },
    { label: 'Values', fields: ['overrides'], render: (formik) => <ValuesStep formik={formik} /> },
  ];

  return (
    <StepperFormDialog<PolicyFormValues>
      open
      title="New TRACKING policy version"
      steps={steps}
      initialValues={initialValues}
      validationSchema={policyFormSchema}
      submitLabel="Create version"
      onClose={onClose}
      renderReview={(v) => {
        const payload = toPolicyPayload(v);
        const target =
          v.scope === 'MACHINE' && v.machine !== null
            ? machineLabel(v.machine)
            : v.scope === 'SITE'
              ? (siteName.get(v.site_id) ?? v.site_id)
              : 'Whole tenant';
        return (
          <>
            <KeyValueGrid
              columns={2}
              items={[
                { label: 'Scope', value: SCOPE_LABELS[v.scope] },
                { label: 'Applies to', value: target },
                {
                  label: 'Effective from',
                  value:
                    v.effective_from === '' ? 'Now' : formatInstantIn(v.effective_from, timeZone),
                },
                { label: 'Reason', value: v.reason },
              ]}
            />
            <Typography variant="subtitle2">Overridden values</Typography>
            <KeyValueGrid
              columns={2}
              items={Object.entries(payload.values).map(([key, value]) => {
                const def = TRACKING_FIELDS.find((f) => f.key === key);
                return { label: def?.label ?? key, value: formatPolicyValue(def, value) };
              })}
            />
          </>
        );
      }}
      onSubmit={async (values) => {
        const payload = toPolicyPayload(values);
        try {
          onCreated(await policyService.create('TRACKING', payload, keyFor(payload)));
        } catch (err) {
          throw withPolicyErrorCode(err);
        }
      }}
    />
  );
}
