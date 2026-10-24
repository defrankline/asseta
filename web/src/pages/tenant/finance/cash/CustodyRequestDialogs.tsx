import { Alert } from '@mui/material';
import { useState } from 'react';
import { custodyService } from '../../../../api/services/custodyService';
import type {
  CashReasonDto,
  CashRetentionDto,
  CustodianDto,
  CustodyAdjustmentDto,
} from '../../../../api/custodyTypes';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { FormDialog } from '../../../../components/forms/FormDialog';
import { FormikDateTimeField } from '../../../../components/forms/FormikDateTimeField';
import { FormikSelectField } from '../../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { StepperFormDialog } from '../../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { formatEnteredMoney } from '../../../../utils/money';
import { formatInstantIn } from '../../../../utils/time';
import { withErrorCode } from '../../shared/errorHints';
import { CURRENCY_OPTIONS } from '../../shared/financeDisplay';
import {
  ADJUSTMENT_KIND_LABELS,
  ADJUSTMENT_KIND_OPTIONS,
  CUSTODY_ERROR_HINTS,
  REASON_KIND_OPTIONS,
  REVERSIBLE_ENTITY_LABELS,
  REVERSIBLE_ENTITY_OPTIONS,
} from './custodyDisplay';
import {
  adjustmentSchema,
  reasonSchema,
  retentionSchema,
  toAdjustmentPayload,
  toReasonPayload,
  toRetentionPayload,
  type AdjustmentValues,
  type ReasonValues,
  type RetentionValues,
} from './custodyForms';
import { FormikCashReasonIdPicker, FormikCustodianIdPicker } from './custodyPickers';

const REVERSIBLE_ENTITY_CHOICES = [{ value: '', label: 'None' }, ...REVERSIBLE_ENTITY_OPTIONS];

const hinted = (err: unknown) => withErrorCode(err, CUSTODY_ERROR_HINTS);
const entered = (amount: string, currency: string) => formatEnteredMoney(amount, currency);

// --- retention --------------------------------------------------------------------------------------------
interface RetentionDialogProps {
  /** The caller asks for their own custody (no custodian picker). */
  ownCustody: boolean;
  timeZone: string;
  onClose: () => void;
  onRecorded: (r: CashRetentionDto) => void;
}

/** Ask that a custodian may keep some cash instead of remitting it (an exception to full remittance). */
export function RetentionDialog({
  ownCustody,
  timeZone,
  onClose,
  onRecorded,
}: RetentionDialogProps) {
  const keyFor = useIdempotencyKey();
  const [custodian, setCustodian] = useState<CustodianDto | null>(null);
  const [initial] = useState<RetentionValues>({
    staff_member_id: '',
    amount: '',
    currency: '',
    reason_id: '',
    reason: '',
    valid_until: '',
  });
  return (
    <StepperFormDialog<RetentionValues>
      open
      title="Request to keep cash"
      initialValues={initial}
      validationSchema={retentionSchema}
      submitLabel="Send request"
      onClose={onClose}
      steps={[
        {
          label: 'Amount',
          fields: ['staff_member_id', 'amount', 'currency'],
          render: () => (
            <>
              {!ownCustody && (
                <FormikCustodianIdPicker
                  name="staff_member_id"
                  label="Custodian"
                  helperText="Leave empty for your own custody."
                  onOptionChange={setCustodian}
                />
              )}
              <FormikTextField
                name="amount"
                label="Amount to keep"
                required
                slotProps={{ htmlInput: { inputMode: 'decimal' } }}
              />
              <FormikSelectField name="currency" label="Currency" options={CURRENCY_OPTIONS} />
            </>
          ),
        },
        {
          label: 'Reason',
          fields: ['reason_id', 'reason', 'valid_until'],
          render: () => (
            <>
              <FormikCashReasonIdPicker
                kind="RETENTION"
                name="reason_id"
                label="Reason (from the tenant's list)"
                helperText="Required when your organisation keeps a retention reason list."
              />
              <FormikTextField
                name="reason"
                label="Why the cash is kept"
                required
                multiline
                minRows={2}
              />
              <FormikDateTimeField
                name="valid_until"
                label="Valid until (optional)"
                timeZone={timeZone}
              />
            </>
          ),
        },
      ]}
      renderReview={(v) => (
        <>
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Custodian', value: custodian?.full_name ?? 'Me (my custody)' },
              { label: 'Amount to keep', value: entered(v.amount, v.currency) },
              { label: 'Reason', value: v.reason.trim() },
              {
                label: 'Valid until',
                value: v.valid_until === '' ? '—' : formatInstantIn(v.valid_until, timeZone),
              },
            ]}
          />
          <Alert severity="info">
            Someone else with the approval permission decides. Until it is approved, the full
            balance is expected at remittance.
          </Alert>
        </>
      )}
      onSubmit={async (v) => {
        const body = toRetentionPayload(v);
        try {
          onRecorded(await custodyService.requestRetention(body, keyFor(body)));
        } catch (err) {
          throw hinted(err);
        }
      }}
    />
  );
}

// --- custody adjustment -----------------------------------------------------------------------------------
interface AdjustmentDialogProps {
  staffMemberId?: string;
  timeZone: string;
  onClose: () => void;
  onRecorded: (a: CustodyAdjustmentDto) => void;
}

/** Propose a reversal or adjustment of a custodian's expected balance; it counts once someone else approves. */
export function AdjustmentDialog({
  staffMemberId = '',
  timeZone,
  onClose,
  onRecorded,
}: AdjustmentDialogProps) {
  const keyFor = useIdempotencyKey();
  const [custodian, setCustodian] = useState<CustodianDto | null>(null);
  const [initial] = useState<AdjustmentValues>({
    staff_member_id: staffMemberId,
    kind: 'ADJUSTMENT',
    amount: '',
    currency: '',
    reason_id: '',
    reason: '',
    reverses_entity_type: '',
    reverses_entity_id: '',
    occurred_at: '',
  });
  return (
    <StepperFormDialog<AdjustmentValues>
      open
      title="Propose custody adjustment"
      initialValues={initial}
      validationSchema={adjustmentSchema}
      submitLabel="Propose adjustment"
      onClose={onClose}
      steps={[
        {
          label: 'Adjustment',
          fields: ['staff_member_id', 'kind', 'amount', 'currency'],
          render: () => (
            <>
              <FormikCustodianIdPicker
                name="staff_member_id"
                label="Custodian"
                required
                onOptionChange={setCustodian}
              />
              <FormikSelectField name="kind" label="Kind" options={ADJUSTMENT_KIND_OPTIONS} />
              <FormikTextField
                name="amount"
                label="Amount"
                required
                helperText="Positive raises the expected balance; negative (e.g. -5000) lowers it."
              />
              <FormikSelectField name="currency" label="Currency" options={CURRENCY_OPTIONS} />
            </>
          ),
        },
        {
          label: 'Reason',
          fields: [
            'reason_id',
            'reason',
            'reverses_entity_type',
            'reverses_entity_id',
            'occurred_at',
          ],
          render: (f) => (
            <>
              <FormikCashReasonIdPicker
                kind="ADJUSTMENT"
                name="reason_id"
                label="Reason (from the tenant's list)"
                helperText="Required when your organisation keeps an adjustment reason list."
              />
              <FormikTextField name="reason" label="Reason" required multiline minRows={2} />
              <FormikSelectField
                name="reverses_entity_type"
                label={
                  f.values.kind === 'REVERSAL' ? 'Record reversed' : 'Record reversed (optional)'
                }
                options={REVERSIBLE_ENTITY_CHOICES}
              />
              <FormikTextField
                name="reverses_entity_id"
                label={f.values.kind === 'REVERSAL' ? 'Record id' : 'Record id (optional)'}
                helperText="Copy it from the reconciliation drill-down."
              />
              <FormikDateTimeField
                name="occurred_at"
                label="Effective at (optional, default now)"
                timeZone={timeZone}
              />
            </>
          ),
        },
      ]}
      renderReview={(v) => (
        <>
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Custodian', value: custodian?.full_name ?? v.staff_member_id },
              { label: 'Kind', value: ADJUSTMENT_KIND_LABELS[v.kind] },
              { label: 'Amount', value: v.amount.trim() + (v.currency ? ` ${v.currency}` : '') },
              { label: 'Reason', value: v.reason.trim() },
              {
                label: 'Record reversed',
                value:
                  v.reverses_entity_type === ''
                    ? '—'
                    : `${REVERSIBLE_ENTITY_LABELS[v.reverses_entity_type]} ${v.reverses_entity_id}`,
              },
            ]}
          />
          <Alert severity="info">
            The adjustment counts in the custodian’s expected balance only after someone else
            approves it.
          </Alert>
        </>
      )}
      onSubmit={async (v) => {
        const body = toAdjustmentPayload(v);
        try {
          onRecorded(await custodyService.proposeAdjustment(body, keyFor(body)));
        } catch (err) {
          throw hinted(err);
        }
      }}
    />
  );
}

// --- reason lists -----------------------------------------------------------------------------------------
interface ReasonDialogProps {
  reason?: CashReasonDto;
  onClose: () => void;
  onSaved: (r: CashReasonDto) => void;
}

/** Create or edit an entry of the tenant's cash reason lists (the kind is fixed once created). */
export function ReasonDialog({ reason, onClose, onSaved }: ReasonDialogProps) {
  const keyFor = useIdempotencyKey();
  const editing = reason !== undefined;
  return (
    <FormDialog<ReasonValues>
      open
      title={editing ? 'Edit cash reason' : 'New cash reason'}
      initialValues={{
        kind: reason?.kind ?? 'VARIANCE',
        label: reason?.label ?? '',
        description: reason?.description ?? '',
      }}
      validationSchema={reasonSchema}
      submitLabel={editing ? 'Save' : 'Create'}
      onClose={onClose}
      onSubmit={async (v) => {
        try {
          if (reason === undefined) {
            const body = toReasonPayload(v);
            onSaved(await custodyService.createReason(body, keyFor(body)));
          } else {
            const body = {
              label: v.label.trim(),
              description: v.description.trim() === '' ? null : v.description.trim(),
              version: reason.version,
            };
            onSaved(await custodyService.updateReason(reason.id, body, keyFor(body)));
          }
        } catch (err) {
          throw hinted(err);
        }
      }}
    >
      <FormikSelectField
        name="kind"
        label="List"
        options={REASON_KIND_OPTIONS}
        disabled={editing}
      />
      <FormikTextField name="label" label="Label" required />
      <FormikTextField name="description" label="Description (optional)" multiline minRows={2} />
    </FormDialog>
  );
}
