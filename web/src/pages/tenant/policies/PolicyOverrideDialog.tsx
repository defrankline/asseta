import { Alert, Box, MenuItem, TextField, Typography } from '@mui/material';
import { getIn, type FormikProps } from 'formik';
import { useCallback, useState } from 'react';
import { policyService } from '../../../api/services/policyService';
import type {
  CategoryDto,
  JobSiteDto,
  MachineDto,
  PolicyType,
  PolicyVersionDto,
  StaffDto,
} from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { DateTimeField } from '../../../components/forms/DateTimeField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatInstantIn } from '../../../utils/time';
import { machineLabel } from '../shared/display';
import { FormikStaffIdPicker } from '../shared/financePickers';
import { FormikCategoryPicker, FormikJobSitePicker } from '../shared/lookupPickers';
import { categoryLabel, jobSiteLabel } from '../shared/lookups';
import { MachinePicker } from '../shared/MachinePicker';
import { OverrideFieldInput } from './OverrideFieldInput';
import { withPolicyErrorCode } from './policyErrors';
import {
  allowedFields,
  findField,
  formatPolicyValue,
  POLICY_FIELDS,
  POLICY_TYPE_LABELS,
  scopesFor,
  type OverrideScope,
} from './policyFields';
import {
  initialPolicyValues,
  policyFormSchema,
  toPolicyPayload,
  type PolicyFormValues,
} from './policyForm';

interface PolicyOverrideDialogProps {
  policyType: PolicyType;
  initialScope: OverrideScope;
  initialMachine: MachineDto | null;
  initialSiteId: string;
  /** STAFF scope: the staff member chosen on the page ('' = none). */
  initialStaffId?: string;
  /** MACHINE_CATEGORY scope: the category chosen on the page ('' = none). */
  initialCategoryId?: string;
  /** Current effective values, used to prefill inputs. */
  current: Record<string, unknown> | null;
  sites: readonly JobSiteDto[] | null;
  timeZone: string;
  onClose: () => void;
  onCreated: (version: PolicyVersionDto) => void;
}

const SCOPE_ORDER: readonly OverrideScope[] = [
  'TENANT',
  'MACHINE_CATEGORY',
  'MACHINE',
  'SITE',
  'STAFF',
];
const SCOPE_LABELS: Readonly<Record<OverrideScope, string>> = {
  TENANT: 'Tenant default (all fields)',
  MACHINE_CATEGORY: 'Machine category override',
  MACHINE: 'Machine override',
  SITE: 'Site override',
  STAFF: 'Staff member override',
};

const SCOPE_NOUNS: Readonly<Record<OverrideScope, string>> = {
  TENANT: 'tenant',
  MACHINE_CATEGORY: 'machine category',
  MACHINE: 'machine',
  SITE: 'site',
  STAFF: 'staff member',
};

function ScopeStep({
  formik,
  sites,
  timeZone,
  onSiteChange,
  onStaffChange,
  onCategoryChange,
}: {
  formik: FormikProps<PolicyFormValues>;
  sites: readonly JobSiteDto[] | null;
  timeZone: string;
  onSiteChange: (site: JobSiteDto | null) => void;
  onStaffChange: (staff: StaffDto | null) => void;
  onCategoryChange: (category: CategoryDto | null) => void;
}) {
  const { values, setFieldValue, touched, errors } = formik;
  /** The page already holds the job sites (for labels): resolve a preselected id from them. */
  const resolveSite = useCallback(
    (id: string) => Promise.resolve(sites?.find((s) => s.id === id) ?? null),
    [sites],
  );
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
          for (const def of POLICY_FIELDS[values.policy_type]) {
            void setFieldValue(`overrides.${def.key}.enabled`, false, false);
          }
        }}
        fullWidth
      >
        {SCOPE_ORDER.map((s) =>
          scopesFor(values.policy_type).includes(s) && (s !== 'SITE' || sites !== null) ? (
            <MenuItem key={s} value={s}>
              {SCOPE_LABELS[s]}
            </MenuItem>
          ) : null,
        )}
      </TextField>
      {values.scope === 'MACHINE_CATEGORY' && (
        <FormikCategoryPicker
          name="category_id"
          label="Machine category"
          required
          onOptionChange={onCategoryChange}
          helperText="Machines of this category use this value unless a machine has its own."
        />
      )}
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
        <FormikJobSitePicker
          name="site_id"
          label="Job site"
          required
          resolveOption={resolveSite}
          onOptionChange={onSiteChange}
        />
      )}
      {values.scope === 'STAFF' && (
        <FormikStaffIdPicker
          name="staff_id"
          label="Staff member"
          required
          onOptionChange={onStaffChange}
          helperText="This person's own value replaces the site and tenant values."
        />
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
  const fields = allowedFields(formik.values.policy_type, formik.values.scope);
  const groupError: unknown = formik.errors.overrides;
  return (
    <>
      <Alert severity="info">
        {formik.values.scope === 'TENANT'
          ? 'Tenant defaults may set every field.'
          : `Only these fields may be overridden for a ${SCOPE_NOUNS[formik.values.scope]}.`}
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
  const { policyType, sites, timeZone, onClose, onCreated } = props;
  const keyFor = useIdempotencyKey();
  const [initialValues] = useState(() =>
    initialPolicyValues(
      policyType,
      scopesFor(policyType).includes(props.initialScope) ? props.initialScope : 'TENANT',
      props.current,
      props.initialMachine,
      props.initialSiteId,
      props.initialStaffId ?? '',
      props.initialCategoryId ?? '',
    ),
  );
  const [site, setSite] = useState<JobSiteDto | null>(null);
  const [staff, setStaff] = useState<StaffDto | null>(null);
  const [category, setCategory] = useState<CategoryDto | null>(null);

  const steps: FormStep<PolicyFormValues>[] = [
    {
      label: 'Scope',
      fields: ['scope', 'machine', 'site_id', 'staff_id', 'category_id', 'reason'],
      render: (formik) => (
        <ScopeStep
          formik={formik}
          sites={sites}
          timeZone={timeZone}
          onSiteChange={setSite}
          onStaffChange={setStaff}
          onCategoryChange={setCategory}
        />
      ),
    },
    { label: 'Values', fields: ['overrides'], render: (formik) => <ValuesStep formik={formik} /> },
  ];

  return (
    <StepperFormDialog<PolicyFormValues>
      open
      title={`New ${POLICY_TYPE_LABELS[policyType].toLowerCase()} policy version`}
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
              ? site?.id === v.site_id
                ? jobSiteLabel(site)
                : v.site_id
              : v.scope === 'STAFF'
                ? staff?.id === v.staff_id
                  ? staff.full_name
                  : v.staff_id
                : v.scope === 'MACHINE_CATEGORY'
                  ? category?.id === v.category_id
                    ? categoryLabel(category)
                    : v.category_id
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
                const def = findField(policyType, key);
                return { label: def?.label ?? key, value: formatPolicyValue(def, value) };
              })}
            />
          </>
        );
      }}
      onSubmit={async (values) => {
        const payload = toPolicyPayload(values);
        try {
          onCreated(await policyService.create(policyType, payload, keyFor(payload)));
        } catch (err) {
          throw withPolicyErrorCode(err);
        }
      }}
    />
  );
}
