import { Alert } from '@mui/material';
import { useState } from 'react';
import { newUuid } from '../../../../api/ids';
import { cashService } from '../../../../api/services/cashService';
import type { CashCustodyEntryDto, CashHandoverDto, StaffDto } from '../../../../api/types';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { FormikDateTimeField } from '../../../../components/forms/FormikDateTimeField';
import { FormikSelectField } from '../../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { StepperFormDialog } from '../../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { formatInstantIn } from '../../../../utils/time';
import { withErrorCode } from '../../shared/errorHints';
import { CURRENCY_OPTIONS, FINANCE_ERROR_HINTS } from '../../shared/financeDisplay';
import { FormikStaffIdPicker } from '../../shared/financePickers';
import {
  ENTRY_TYPE_OPTIONS,
  floatSchema,
  handoverSchema,
  toFloatPayload,
  toHandoverPayload,
  type FloatValues,
  type HandoverValues,
} from './cashForms';

const amountText = (amount: string, currency: string) =>
  `${amount} ${currency === '' ? '(tenant base currency)' : currency}`;

interface FloatDialogProps {
  staffMemberId?: string;
  timeZone: string;
  onClose: () => void;
  onRecorded: (entry: CashCustodyEntryDto) => void;
}

/** Office issues a float (or records an opening balance) into a supervisor's custody. */
export function FloatDialog({
  staffMemberId = '',
  timeZone,
  onClose,
  onRecorded,
}: FloatDialogProps) {
  const keyFor = useIdempotencyKey();
  const [staff, setStaff] = useState<StaffDto | null>(null);
  const [initial] = useState<FloatValues>(() => ({
    staff_member_id: staffMemberId,
    entry_type: 'FLOAT_ISSUED',
    amount: '',
    currency: '',
    occurred_at: new Date().toISOString(),
    reference: '',
    note: '',
  }));
  return (
    <StepperFormDialog<FloatValues>
      open
      title="Record cash float"
      initialValues={initial}
      validationSchema={floatSchema}
      submitLabel="Record float"
      onClose={onClose}
      steps={[
        {
          label: 'Float',
          fields: ['staff_member_id', 'entry_type', 'amount', 'currency'],
          render: () => (
            <>
              <FormikStaffIdPicker
                name="staff_member_id"
                label="Supervisor (custodian)"
                supervisorsOnly
                required
                onOptionChange={setStaff}
              />
              <FormikSelectField name="entry_type" label="Entry" options={ENTRY_TYPE_OPTIONS} />
              <FormikTextField name="amount" label="Amount" required />
              <FormikSelectField name="currency" label="Currency" options={CURRENCY_OPTIONS} />
            </>
          ),
        },
        {
          label: 'Details',
          fields: ['occurred_at', 'reference', 'note'],
          render: () => (
            <>
              <FormikDateTimeField
                name="occurred_at"
                label="Issued at"
                timeZone={timeZone}
                required
              />
              <FormikTextField name="reference" label="Reference (optional)" />
              <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
            </>
          ),
        },
      ]}
      renderReview={(v) => (
        <>
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Supervisor', value: staff?.full_name ?? v.staff_member_id },
              {
                label: 'Entry',
                value: v.entry_type === 'FLOAT_ISSUED' ? 'Float issued' : 'Opening balance',
              },
              { label: 'Amount', value: amountText(v.amount, v.currency) },
              { label: 'Issued at', value: formatInstantIn(v.occurred_at, timeZone) },
            ]}
          />
          <Alert severity="info">
            The amount is added to the supervisor’s outstanding cash accountability.
          </Alert>
        </>
      )}
      onSubmit={async (v) => {
        const body = toFloatPayload(v);
        try {
          onRecorded(await cashService.issueFloat(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, FINANCE_ERROR_HINTS);
        }
      }}
    />
  );
}

interface HandoverDialogProps {
  staffMemberId?: string;
  timeZone: string;
  onClose: () => void;
  onRecorded: (handover: CashHandoverDto) => void;
}

/** A supervisor hands cash to the office; CLAIMED until someone else verifies it. */
export function HandoverDialog({
  staffMemberId = '',
  timeZone,
  onClose,
  onRecorded,
}: HandoverDialogProps) {
  const keyFor = useIdempotencyKey();
  const [clientId] = useState(() => newUuid());
  const [staff, setStaff] = useState<StaffDto | null>(null);
  const [initial] = useState<HandoverValues>(() => ({
    staff_member_id: staffMemberId,
    amount: '',
    currency: '',
    handed_at: new Date().toISOString(),
    reference: '',
    note: '',
  }));
  return (
    <StepperFormDialog<HandoverValues>
      open
      title="Record cash handover"
      initialValues={initial}
      validationSchema={handoverSchema}
      submitLabel="Record handover"
      onClose={onClose}
      steps={[
        {
          label: 'Handover',
          fields: ['staff_member_id', 'amount', 'currency'],
          render: () => (
            <>
              <FormikStaffIdPicker
                name="staff_member_id"
                label="Handed over by (custodian)"
                supervisorsOnly
                onOptionChange={setStaff}
                helperText="Leave empty for your own custody. Someone else's needs office cash permission (NOT_CUSTODIAN)."
              />
              <FormikTextField name="amount" label="Amount" required />
              <FormikSelectField name="currency" label="Currency" options={CURRENCY_OPTIONS} />
            </>
          ),
        },
        {
          label: 'Details',
          fields: ['handed_at', 'reference', 'note'],
          render: () => (
            <>
              <FormikDateTimeField
                name="handed_at"
                label="Handed over at"
                timeZone={timeZone}
                required
              />
              <FormikTextField name="reference" label="Reference (optional, e.g. deposit slip)" />
              <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
            </>
          ),
        },
      ]}
      renderReview={(v) => (
        <>
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Custodian', value: staff?.full_name ?? 'Me (my custody)' },
              { label: 'Amount', value: amountText(v.amount, v.currency) },
              { label: 'Handed over at', value: formatInstantIn(v.handed_at, timeZone) },
              { label: 'Reference', value: v.reference.trim() || '—' },
            ]}
          />
          <Alert severity="info">
            Recorded as CLAIMED. It reduces the custodian’s outstanding cash only after someone else
            verifies it (segregation of duties).
          </Alert>
        </>
      )}
      onSubmit={async (v) => {
        const body = toHandoverPayload(v, clientId);
        try {
          onRecorded(await cashService.recordHandover(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, FINANCE_ERROR_HINTS);
        }
      }}
    />
  );
}
