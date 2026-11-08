import { Alert } from '@mui/material';
import { useMemo } from 'react';
import { object, string, type ObjectSchema } from 'yup';
import { custodyService } from '../../../../api/services/custodyService';
import type {
  CashVarianceDto,
  VarianceAssigneeDto,
  VarianceOutcome,
} from '../../../../api/custodyTypes';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { FormDialog } from '../../../../components/forms/FormDialog';
import { FormikAsyncIdAutocomplete } from '../../../../components/forms/FormikAsyncIdAutocomplete';
import { FormikSelectField } from '../../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { FormikEvidenceField } from '../../shared/EvidenceField';
import { evidenceIds } from '../../shared/evidenceRules';
import { withErrorCode } from '../../shared/errorHints';
import type { Option } from '../../shared/display';
import {
  CUSTODY_ERROR_HINTS,
  VARIANCE_KIND_LABELS,
  VARIANCE_OUTCOME_LABELS,
  VARIANCE_SOURCE_LABELS,
} from './custodyDisplay';
import {
  explainVarianceSchema,
  resolveVarianceSchemaFor,
  toResolveVariancePayload,
  toWriteOffPayload,
  writeOffSchema,
  type ExplainVarianceValues,
  type ResolveVarianceValues,
  type WriteOffValues,
} from './custodyForms';
import { searchVarianceAssignees } from './custodyHooks';
import { FormikCashReasonIdPicker } from './custodyPickers';
import { varianceFigure, type VarianceFigureKey } from './varianceFigures';

const hinted = (err: unknown) => withErrorCode(err, CUSTODY_ERROR_HINTS);

const OUTCOME = (value: VarianceOutcome): Option<VarianceOutcome> => ({
  value,
  label: VARIANCE_OUTCOME_LABELS[value],
});

/** Hour differences are explained or corrected; money can also be recovered or written off. */
const HOURS_OUTCOME_OPTIONS = [OUTCOME('EXPLAINED'), OUTCOME('CORRECTED_ERROR')];
const MONEY_OUTCOME_OPTIONS = [OUTCOME('RECOVERED'), OUTCOME('CORRECTED_ERROR')];
const MONEY_OUTCOME_WRITE_OFF_OPTIONS = [...MONEY_OUTCOME_OPTIONS, OUTCOME('WRITTEN_OFF')];

const FIGURES: readonly [string, VarianceFigureKey][] = [
  ['Declared', 'declared_amount'],
  ['Received', 'received_amount'],
  ['Difference', 'amount'],
];

export function VarianceSummary({ v, custodian }: { v: CashVarianceDto; custodian: string }) {
  return (
    <KeyValueGrid
      columns={2}
      items={[
        { label: 'From', value: VARIANCE_SOURCE_LABELS[v.source_type] },
        { label: 'Kind', value: VARIANCE_KIND_LABELS[v.kind] },
        { label: 'Accountable custodian', value: custodian },
        ...FIGURES.map(([label, key]) => ({ label, value: varianceFigure(v, key) })),
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

/**
 * Close an open variance with its outcome and evidence. With a second person required this only
 * proposes the closure; someone else decides it.
 */
export function ResolveVarianceDialog({
  variance,
  custodian,
  allowWriteOff,
  secondPerson,
  evidenceRequired,
  onDone,
  onClose,
}: VarianceDialogProps & {
  allowWriteOff: boolean;
  secondPerson: boolean;
  evidenceRequired: boolean;
}) {
  const keyFor = useIdempotencyKey();
  const schema = useMemo(() => resolveVarianceSchemaFor(evidenceRequired), [evidenceRequired]);
  const label = secondPerson ? 'Propose closure' : 'Resolve';
  return (
    <FormDialog<ResolveVarianceValues>
      open
      title={secondPerson ? 'Propose closing this variance' : 'Resolve variance'}
      initialValues={{ outcome: '', reason_id: '', note: '', evidence: [] }}
      validationSchema={schema}
      submitLabel={label}
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
      {secondPerson && (
        <Alert severity="info">
          Your company policy needs a second person: someone else decides this closure.
        </Alert>
      )}
      {variance.unit === 'HOURS' ? (
        <FormikSelectField
          name="outcome"
          label="Outcome"
          options={HOURS_OUTCOME_OPTIONS}
          required
        />
      ) : allowWriteOff ? (
        <FormikSelectField
          name="outcome"
          label="Outcome"
          options={MONEY_OUTCOME_WRITE_OFF_OPTIONS}
          required
        />
      ) : (
        <FormikSelectField
          name="outcome"
          label="Outcome"
          options={MONEY_OUTCOME_OPTIONS}
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
      <FormikEvidenceField required={evidenceRequired} />
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

const assigneeLabel = (a: VarianceAssigneeDto) =>
  a.email === null ? a.display_name : `${a.display_name} (${a.email})`;

interface AssignValues {
  assignee_user_id: string;
}
const assignSchema: ObjectSchema<AssignValues> = object({
  assignee_user_id: string().required('Choose who investigates this'),
});

/** Give the variance to someone holding the variance permission (never a party to it). */
export function AssignVarianceDialog({
  variance,
  custodian,
  onDone,
  onClose,
}: VarianceDialogProps) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<AssignValues>
      open
      title="Assign variance"
      initialValues={{ assignee_user_id: variance.assignee_user_id ?? '' }}
      validationSchema={assignSchema}
      submitLabel="Assign"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = { assignee_user_id: v.assignee_user_id };
        try {
          onDone(await custodyService.assignVariance(variance.id, body, keyFor(body)));
        } catch (err) {
          throw hinted(err);
        }
      }}
    >
      <VarianceSummary v={variance} custodian={custodian} />
      <FormikAsyncIdAutocomplete<VarianceAssigneeDto>
        name="assignee_user_id"
        label="Assigned to"
        required
        fetchOptions={searchVarianceAssignees}
        getOptionId={(a) => a.user_id}
        getOptionLabel={assigneeLabel}
        noOptionsText="Nobody with the variance permission matches"
      />
    </FormDialog>
  );
}

/** Record what the investigation found, with its evidence; closing it is a separate step. */
export function ExplainVarianceDialog({
  variance,
  custodian,
  onDone,
  onClose,
}: VarianceDialogProps) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<ExplainVarianceValues>
      open
      title="Explain variance"
      initialValues={{ explanation: variance.explanation ?? '', evidence: [] }}
      validationSchema={explainVarianceSchema}
      submitLabel="Save explanation"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = {
          explanation: v.explanation.trim(),
          evidence_attachment_ids: evidenceIds(v.evidence),
        };
        try {
          onDone(await custodyService.explainVariance(variance.id, body, keyFor(body)));
        } catch (err) {
          throw hinted(err);
        }
      }}
    >
      <VarianceSummary v={variance} custodian={custodian} />
      <FormikTextField name="explanation" label="What happened" required multiline minRows={3} />
      <FormikEvidenceField />
    </FormDialog>
  );
}
