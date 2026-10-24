import { Alert, Box, Button, Chip, Typography } from '@mui/material';
import { useFormikContext } from 'formik';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { expenseService } from '../../../api/services/expenseService';
import { policyService } from '../../../api/services/policyService';
import { newIdempotencyKey } from '../../../api/ids';
import type { AttachmentDto, EffectivePolicyDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { AttachmentUpload } from '../../../components/meter/AttachmentUpload';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useSession } from '../../../session/useSession';
import { attemptGpsFix } from '../../../utils/geolocation';
import type { ExpenseFormValues } from './expenseForm';

const show = (v: unknown): string =>
  v === undefined || v === null ? '—' : typeof v === 'string' ? v : JSON.stringify(v);

/** EXPENSE_CAPTURE policy in force at the incurred time: receipt / GPS rules and approval limit. */
export function ExpensePolicySummary({ at }: { at: string }) {
  const { hasPermission } = useSession();
  // Expense writers may read the EXPENSE_CAPTURE policy they submit under (as the field apps do).
  const canRead = hasPermission(
    [PERMISSIONS.tenantPolicyRead, PERMISSIONS.tenantExpenseWrite],
    'any',
  );
  const load = useCallback(
    (signal: AbortSignal): Promise<EffectivePolicyDto> =>
      policyService.effective('EXPENSE_CAPTURE', { at }, signal),
    [at],
  );
  const res = useAsyncResource(load, [], canRead);
  if (!canRead) {
    return (
      <Alert severity="info">
        The EXPENSE_CAPTURE policy decides whether a receipt and GPS are required and whether this
        expense is auto-approved; the server applies it on submit.
      </Alert>
    );
  }
  if (res.data === null) return null;
  const v = res.data.values;
  return (
    <Alert severity="info">
      <Typography variant="body2" sx={{ fontWeight: 600 }}>
        EXPENSE_CAPTURE policy {res.data.version_stamp}
      </Typography>
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Receipt required above', value: show(v.receipt_required_above) },
          { label: 'Auto-approved up to', value: show(v.auto_approve_limit) },
          { label: 'GPS required', value: v.gps_required === true ? 'Yes' : 'No' },
          { label: 'GPS max accuracy (m)', value: show(v.gps_max_accuracy_m) },
        ]}
      />
      <Typography variant="caption">
        Amounts in the tenant base currency; foreign-currency expenses always need a receipt and
        approval.
      </Typography>
    </Alert>
  );
}

/** Receipts (uploaded immediately, kept as attachment ids) and one honest browser GPS attempt. */
export function ExpenseEvidenceStep() {
  const { values, setFieldValue } = useFormikContext<ExpenseFormValues>();
  const [locating, setLocating] = useState(false);
  const upload = (file: File) => expenseService.uploadReceipt(file, newIdempotencyKey());
  const add = (a: AttachmentDto | null) => {
    if (a !== null) void setFieldValue('receipts', [...values.receipts, a]);
  };
  const gps = values.gps;
  return (
    <Box className="flex flex-col gap-3">
      <ExpensePolicySummary at={values.incurred_at} />
      <Box className="flex flex-wrap gap-1">
        {values.receipts.map((r, i) => (
          <Chip
            key={r.id}
            label={`Receipt ${String(i + 1)} · ${r.sha256.slice(0, 10)}…`}
            onDelete={() => {
              void setFieldValue(
                'receipts',
                values.receipts.filter((x) => x.id !== r.id),
              );
            }}
          />
        ))}
      </Box>
      <AttachmentUpload
        label="Add receipt photo"
        value={null}
        onChange={add}
        upload={upload}
        accept="image/*,application/pdf"
        helperText="Uploaded originals are stored immutably with their SHA-256."
        disabled={values.receipts.length >= 10}
      />
      <Box className="flex flex-wrap items-center gap-2">
        <Button
          variant="outlined"
          size="small"
          loading={locating}
          onClick={() => {
            setLocating(true);
            void attemptGpsFix().then((fix) => {
              setLocating(false);
              void setFieldValue('gps', fix);
            });
          }}
        >
          {gps === null ? 'Capture GPS' : 'Capture GPS again'}
        </Button>
        <Typography variant="body2">
          {gps === null
            ? 'No GPS attempt yet (optional unless the policy requires it).'
            : gps.status === 'FIX'
              ? `Fix ${String(gps.latitude)}, ${String(gps.longitude)} ±${String(Math.round(gps.accuracy_m ?? 0))} m`
              : `No fix: ${gps.status}`}
        </Typography>
      </Box>
    </Box>
  );
}
