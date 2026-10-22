import { Typography } from '@mui/material';
import dayjs from 'dayjs';
import { useRef } from 'react';
import { object, string } from 'yup';
import { withErrorCode } from '../../../api/lifecycle';
import { platformMlService } from '../../../api/services/platformMlService';
import type { MlSnapshotRunDto, MlTrainingRunDto, TenantDto } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import { FormikDateField } from '../../../components/forms/FormikDateField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { resolveTenant, searchTenants, tenantId, tenantLabel } from '../shared/platformLookups';

export type RunKind = 'snapshots' | 'train';

export type RunResult =
  | { kind: 'snapshots'; tenantName: string; result: MlSnapshotRunDto }
  | { kind: 'train'; tenantName: string; result: MlTrainingRunDto };

/** Backend bound: at most 26 week ends per snapshot call. */
const MAX_SNAPSHOT_DAYS = 26 * 7;

interface RunValues {
  tenant_id: string;
  from_date: string;
  to_date: string;
}

const RUN_HINTS: Readonly<Record<string, string>> = {
  INVALID_RANGE: 'Choose an end date on or after the start date.',
};

const SCHEMAS = {
  train: object({
    tenant_id: string().required('Choose a tenant'),
    from_date: string().defined(),
    to_date: string().defined(),
  }),
  snapshots: object({
    tenant_id: string().required('Choose a tenant'),
    from_date: string().required('Choose a start date'),
    to_date: string()
      .required('Choose an end date')
      .test('after', 'The end date must be on or after the start date', function check(v) {
        const from = (this.parent as RunValues).from_date;
        return from === '' || v >= from;
      })
      .test('bound', 'At most 26 weeks per run', function check(v) {
        const from = (this.parent as RunValues).from_date;
        return from === '' || dayjs(v).diff(dayjs(from), 'day') <= MAX_SNAPSHOT_DAYS;
      }),
  }),
} as const;

const COPY: Readonly<Record<RunKind, { title: string; confirm: string; effect: string }>> = {
  snapshots: {
    title: 'Refresh feature snapshots',
    confirm: 'Refresh snapshots',
    effect:
      'Computes weekly point-in-time feature snapshots for the tenant from observed facts. Existing week snapshots are kept; future weeks are skipped.',
  },
  train: {
    title: 'Train now',
    confirm: 'Train now',
    effect:
      'Re-assesses readiness and, when there is enough history, trains and evaluates a new model version against the statistical baseline. A new version is never deployed automatically.',
  },
};

interface RunDialogProps {
  kind: RunKind;
  /** The tenant of the row the dialog was opened from; omitted → pick one. */
  tenant: { id: string; name: string } | null;
  onClose: () => void;
  onDone: (result: RunResult) => void;
}

/** Confirms a bounded snapshot or training run for one tenant (platform.ml.manage). */
export function RunDialog({ kind, tenant, onClose, onDone }: RunDialogProps) {
  const keyFor = useIdempotencyKey();
  const copy = COPY[kind];
  const today = dayjs().format('YYYY-MM-DD');
  const initial: RunValues = {
    tenant_id: tenant?.id ?? '',
    from_date: dayjs().subtract(12, 'week').format('YYYY-MM-DD'),
    to_date: today,
  };
  const pickedName = useRef(tenant?.name ?? '');
  return (
    <FormDialog<RunValues>
      open
      title={copy.title}
      initialValues={initial}
      validationSchema={SCHEMAS[kind]}
      submitLabel={copy.confirm}
      onClose={onClose}
      onSubmit={async (v) => {
        const name = pickedName.current === '' ? v.tenant_id : pickedName.current;
        try {
          if (kind === 'snapshots') {
            const body = { from_date: v.from_date, to_date: v.to_date };
            const result = await platformMlService.runSnapshots(
              v.tenant_id,
              body,
              keyFor({ kind, tenant: v.tenant_id, ...body }),
            );
            onDone({ kind, tenantName: name, result });
          } else {
            const result = await platformMlService.runTraining(
              v.tenant_id,
              keyFor({ kind, tenant: v.tenant_id }),
            );
            onDone({ kind, tenantName: name, result });
          }
        } catch (err) {
          throw withErrorCode(err, RUN_HINTS);
        }
      }}
    >
      <Typography variant="body2">{copy.effect}</Typography>
      {tenant === null ? (
        <FormikAsyncIdAutocomplete<TenantDto>
          name="tenant_id"
          label="Tenant"
          required
          fetchOptions={searchTenants}
          getOptionId={tenantId}
          getOptionLabel={tenantLabel}
          resolveOption={resolveTenant}
          onOptionChange={(t) => {
            pickedName.current = t?.display_name ?? '';
          }}
        />
      ) : (
        <Typography variant="body2">
          Tenant: <strong>{tenant.name}</strong>
        </Typography>
      )}
      {kind === 'snapshots' && (
        <>
          <FormikDateField name="from_date" label="From week" required maxDate={today} />
          <FormikDateField name="to_date" label="To week" required maxDate={today} />
        </>
      )}
    </FormDialog>
  );
}
