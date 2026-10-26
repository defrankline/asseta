import { Alert } from '@mui/material';
import { custodyService } from '../../../../api/services/custodyService';
import type { CashVarianceDto } from '../../../../api/custodyTypes';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { FormDialog } from '../../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { withErrorCode } from '../../shared/errorHints';
import {
  CUSTODY_ERROR_HINTS,
  VARIANCE_OUTCOME_OPTIONS,
  VARIANCE_KIND_LABELS,
  VARIANCE_SOURCE_LABELS,
} from './custodyDisplay';
import {
  resolveVarianceSchema,
  toResolveVariancePayload,
  toWriteOffPayload,
  writeOffSchema,
  type ResolveVarianceValues,
  type WriteOffValues,
} from './custodyForms';
import { FormikCashReasonIdPicker } from './custodyPickers';

const OUTCOME_OPTIONS = VARIANCE_OUTCOME_OPTIONS;
const OUTCOME_OPTIONS_NO_WRITE_OFF = VARIANCE_OUTCOME_OPTIONS.filter(
  (o) => o.value !== 'WRITTEN_OFF',
);

const hinted = (err: unknown) => withErrorCode(err, CUSTODY_ERROR_HINTS);

// --- variances --------------------------------------------------------------------------------------------
function VarianceSummary({ v, custodian }: { v: CashVarianceDto; custodian: string }) {
  return (
    <KeyValueGrid
      columns={2}
      items={[
        { label: 'From', value: VARIANCE_SOURCE_LABELS[v.source_type] },
        { label: 'Kind', value: VARIANCE_KIND_LABELS[v.kind] },
        { label: 'Accountable custodian', value: custodian },
        {
          label: 'Declared',
          value: <MoneyText amount={v.declared_amount} currency={v.currency} />,
        },
        {
          label: 'Received',
          value: <MoneyText amount={v.received_amount} currency={v.currency} />,
        },
        {
          label: 'Difference',
          value: <MoneyText amount={v.amount} currency={v.currency} strong />,
        },
      ]}
    />
  );
}

interface VarianceDialogProps {
  variance: CashVarianceDto;
  custodian: string;
  onDone: (v: CashVarianceDto) => void;
  onClose: () => void;
}

/** Resolve an open variance (recovered / corrected error; written off only when no approval is needed). */
export function ResolveVarianceDialog({
  variance,
  custodian,
  allowWriteOff,
  onDone,
  onClose,
}: VarianceDialogProps & { allowWriteOff: boolean }) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<ResolveVarianceValues>
      open
      title="Resolve variance"
      initialValues={{ outcome: '', reason_id: '', note: '' }}
      validationSchema={resolveVarianceSchema}
      submitLabel="Resolve"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = toResolveVariancePayload(v);
        try {
          onDone(await custodyService.resolveVariance(variance.id, body, keyFor(body)));
        } catch (err) {
          throw hinted(err);
        }
      }}
    >
      <VarianceSummary v={variance} custodian={custodian} />
      {allowWriteOff ? (
        <FormikSelectField name="outcome" label="Outcome" options={OUTCOME_OPTIONS} required />
      ) : (
        <FormikSelectField
          name="outcome"
          label="Outcome"
          options={OUTCOME_OPTIONS_NO_WRITE_OFF}
          required
        />
      )}
      <FormikCashReasonIdPicker
        kind="VARIANCE"
        name="reason_id"
        label="Reason (from the tenant's list)"
        helperText="Required when your organisation keeps a variance reason list."
      />
      <FormikTextField name="note" label="Explanation" required multiline minRows={2} />
    </FormDialog>
  );
}

/** Propose writing a variance off; someone else with the write-off permission decides. */
export function WriteOffProposalDialog({
  variance,
  custodian,
  onDone,
  onClose,
}: VarianceDialogProps) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<WriteOffValues>
      open
      title="Propose write-off"
      initialValues={{ reason_id: '', note: '' }}
      validationSchema={writeOffSchema}
      submitLabel="Propose write-off"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = toWriteOffPayload(v);
        try {
          onDone(await custodyService.proposeWriteOff(variance.id, body, keyFor(body)));
        } catch (err) {
          throw hinted(err);
        }
      }}
    >
      <VarianceSummary v={variance} custodian={custodian} />
      <Alert severity="info">
        A write-off lowers the custodian’s expected balance by the difference once someone else
        approves it.
      </Alert>
      <FormikCashReasonIdPicker
        kind="WRITE_OFF"
        name="reason_id"
        label="Write-off reason (from the tenant's list)"
        helperText="Required when your organisation keeps a write-off reason list."
      />
      <FormikTextField name="note" label="Explanation" required multiline minRows={2} />
    </FormDialog>
  );
}
