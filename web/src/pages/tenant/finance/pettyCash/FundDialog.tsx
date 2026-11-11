import { Alert, Stack } from '@mui/material';
import { useState } from 'react';
import type { PettyCashFundDto } from '../../../../api/pettyCashTypes';
import { pettyCashService } from '../../../../api/services/pettyCashService';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { FormikSelectField } from '../../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../../components/forms/StepperFormDialog';
import { StaleVersionAlert } from '../../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../../components/lifecycle/useStaleVersion';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { formatEnteredMoney } from '../../../../utils/money';
import { withErrorCode } from '../../shared/errorHints';
import { CURRENCY_OPTIONS } from '../../shared/financeDisplay';
import { FormikStaffIdPicker } from '../../shared/financePickers';
import { FormikJobSitePicker } from '../../shared/lookupPickers';
import { PETTY_CASH_ERROR_HINTS } from './pettyCashDisplay';
import {
  EMPTY_FUND,
  fundSchema,
  fundValuesFrom,
  toFundPayload,
  toFundUpdate,
  type FundValues,
} from './pettyCashForms';

interface FundDialogProps {
  /** Omitted: create a new fund. */
  fund?: PettyCashFundDto;
  onClose: () => void;
  onSaved: (fund: PettyCashFundDto) => void;
  /** STALE_VERSION on edit: reload the record (the dialog closes). */
  onReload?: () => void;
}

/** Fund → Limits → Review; create, or edit with the `version` that was read. Mount only while open. */
export function FundDialog({ fund, onClose, onSaved, onReload }: FundDialogProps) {
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  const editing = fund !== undefined;
  const [initialValues] = useState<FundValues>(() =>
    fund === undefined ? EMPTY_FUND : fundValuesFrom(fund),
  );
  const [holderName, setHolderName] = useState<string | null>(fund?.holder_staff_name ?? null);
  const steps: FormStep<FundValues>[] = [
    {
      label: 'Fund',
      fields: ['code', 'name', 'holder_staff_id', 'job_site_id'],
      render: () => (
        <>
          <FormikTextField
            name="code"
            label="Code"
            required
            helperText="Short code, e.g. PC-OFFICE."
          />
          <FormikTextField name="name" label="Name" required />
          {editing ? (
            <Alert severity="info">
              Held by {fund.holder_staff_name ?? 'its current holder'}. Use “Change holder” to hand
              the fund to someone else.
            </Alert>
          ) : (
            <FormikStaffIdPicker
              name="holder_staff_id"
              label="Holder (accountable person)"
              required
              onOptionChange={(s) => {
                setHolderName(s?.full_name ?? null);
              }}
            />
          )}
          <FormikJobSitePicker name="job_site_id" label="Job site (optional)" />
        </>
      ),
    },
    {
      label: 'Limits',
      fields: ['currency', 'approved_limit', 'low_balance_level', 'note'],
      render: () => (
        <>
          {!editing && (
            <FormikSelectField name="currency" label="Currency" options={CURRENCY_OPTIONS} />
          )}
          <FormikTextField
            name="approved_limit"
            label="Approved limit"
            required
            helperText="The most the fund holds; top-ups never take it above this."
            slotProps={{ htmlInput: { inputMode: 'decimal' } }}
          />
          <FormikTextField
            name="low_balance_level"
            label="Low-balance level (optional)"
            helperText="Below this, the people who fund it are told."
            slotProps={{ htmlInput: { inputMode: 'decimal' } }}
          />
          <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
        </>
      ),
    },
  ];
  return (
    <StepperFormDialog<FundValues>
      open
      title={editing ? `Edit ${fund.name}` : 'New petty cash fund'}
      steps={steps}
      initialValues={initialValues}
      validationSchema={fundSchema(editing)}
      submitLabel={editing ? 'Save changes' : 'Create fund'}
      onClose={onClose}
      renderReview={(v) => {
        const currency = editing ? fund.currency : v.currency;
        return (
          <Stack spacing={2}>
            {stale && onReload !== undefined && (
              <StaleVersionAlert
                onReload={() => {
                  onReload();
                  onClose();
                }}
              />
            )}
            <KeyValueGrid
              columns={2}
              items={[
                { label: 'Code', value: v.code.trim() || '—' },
                { label: 'Name', value: v.name.trim() || '—' },
                { label: 'Holder', value: holderName ?? '—' },
                { label: 'Currency', value: currency || 'Tenant base currency' },
                { label: 'Approved limit', value: formatEnteredMoney(v.approved_limit, currency) },
                {
                  label: 'Low-balance level',
                  value:
                    v.low_balance_level.trim() === ''
                      ? '—'
                      : formatEnteredMoney(v.low_balance_level, currency),
                },
              ]}
            />
            {!editing && (
              <Alert severity="info">
                A new fund starts empty. Propose its first funding from the fund page; someone else
                approves it and the holder confirms what they received.
              </Alert>
            )}
          </Stack>
        );
      }}
      onSubmit={async (v) => {
        try {
          if (fund === undefined) {
            const body = toFundPayload(v);
            onSaved(await pettyCashService.create(body, keyFor(body)));
          } else {
            const body = toFundUpdate(v, fund.version);
            onSaved(await guard(() => pettyCashService.update(fund.id, body, keyFor(body))));
          }
        } catch (err) {
          throw withErrorCode(err, PETTY_CASH_ERROR_HINTS);
        }
      }}
    />
  );
}
