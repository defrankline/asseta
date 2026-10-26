import { Alert } from '@mui/material';
import { useMemo, useState } from 'react';
import { newUuid } from '../../../../api/ids';
import { cashService } from '../../../../api/services/cashService';
import type { CashCustodyEntryDto, CashHandoverDto, StaffDto } from '../../../../api/types';
import type { CustodianDto, DepositAccountDto } from '../../../../api/custodyTypes';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { FormikDateTimeField } from '../../../../components/forms/FormikDateTimeField';
import { FormikSelectField } from '../../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { StepperFormDialog } from '../../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { formatEnteredMoney } from '../../../../utils/money';
import { formatInstantIn } from '../../../../utils/time';
import { withErrorCode } from '../../shared/errorHints';
import { CURRENCY_OPTIONS, FINANCE_ERROR_HINTS } from '../../shared/financeDisplay';
import { FormikStaffIdPicker } from '../../shared/financePickers';
import {
  ENTRY_TYPE_OPTIONS,
  floatSchema,
  handoverSchemaFor,
  REMITTANCE_METHOD_LABELS,
  toFloatPayload,
  toHandoverPayload,
  type FloatValues,
  type HandoverValues,
} from './cashForms';
import { FormikCustodianIdPicker } from './custodyPickers';
import { RemittanceDepositFields } from './remittanceDeposit';
import { useRemittanceRequirements } from './remittanceDetails';
import { depositAccountLabel } from '../depositAccounts/depositAccountForm';

const amountText = (amount: string, currency: string) => formatEnteredMoney(amount, currency);

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
  /** Field work: the caller hands over their own cash (no custodian picker). */
  ownCustody?: boolean;
  timeZone: string;
  onClose: () => void;
  onRecorded: (handover: CashHandoverDto) => void;
}

/**
 * A custodian remits cash to the company (how it was paid, into which company account, reference
 * and photos); CLAIMED until someone else confirms the amount received.
 */
export function HandoverDialog({
  staffMemberId = '',
  ownCustody = false,
  timeZone,
  onClose,
  onRecorded,
}: HandoverDialogProps) {
  const keyFor = useIdempotencyKey();
  const [clientId] = useState(() => newUuid());
  const [staff, setStaff] = useState<CustodianDto | null>(null);
  const [account, setAccount] = useState<DepositAccountDto | null>(null);
  const requirements = useRemittanceRequirements();
  const schema = useMemo(() => handoverSchemaFor(requirements), [requirements]);
  const [initial] = useState<HandoverValues>(() => ({
    staff_member_id: staffMemberId,
    amount: '',
    currency: '',
    method: 'CASH_TO_OFFICE',
    deposit_account_id: '',
    reference: '',
    evidence: [],
    handed_at: new Date().toISOString(),
    note: '',
  }));
  return (
    <StepperFormDialog<HandoverValues>
      open
      title="Record remittance"
      initialValues={initial}
      validationSchema={schema}
      submitLabel="Record remittance"
      onClose={onClose}
      steps={[
        {
          label: 'Handover',
          fields: ['staff_member_id', 'amount', 'currency'],
          render: () => (
            <>
              {!ownCustody && (
                <FormikCustodianIdPicker
                  name="staff_member_id"
                  label="Handed over by (custodian)"
                  onOptionChange={setStaff}
                  helperText="Leave empty for your own custody. Someone else's needs office cash permission or the tenant's permission for recorders."
                />
              )}
              <FormikTextField name="amount" label="Amount" required />
              <FormikSelectField name="currency" label="Currency" options={CURRENCY_OPTIONS} />
            </>
          ),
        },
        {
          label: 'Deposit',
          fields: ['method', 'deposit_account_id', 'reference', 'evidence'],
          render: () => (
            <RemittanceDepositFields
              requirements={requirements}
              account={account}
              onAccountChange={setAccount}
            />
          ),
        },
        {
          label: 'Details',
          fields: ['handed_at', 'note'],
          render: () => (
            <>
              <FormikDateTimeField
                name="handed_at"
                label="Handed over at"
                timeZone={timeZone}
                required
              />
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
              { label: 'Paid by', value: REMITTANCE_METHOD_LABELS[v.method] },
              {
                label: 'Company account',
                value:
                  account !== null && account.id === v.deposit_account_id
                    ? depositAccountLabel(account)
                    : '—',
              },
              { label: 'Reference', value: v.reference.trim() || '—' },
              {
                label: 'Photos',
                value: v.evidence.length === 0 ? 'None' : String(v.evidence.length),
              },
              { label: 'Handed over at', value: formatInstantIn(v.handed_at, timeZone) },
            ]}
          />
          <Alert severity="info">
            Recorded as awaiting confirmation. It reduces the custodian’s outstanding cash only
            after someone else confirms the amount received (segregation of duties).
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
