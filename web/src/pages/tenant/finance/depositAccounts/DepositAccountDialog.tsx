import { Alert, Box, Stack } from '@mui/material';
import { useState } from 'react';
import type { DepositAccountDto } from '../../../../api/custodyTypes';
import { depositAccountService } from '../../../../api/services/depositAccountService';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { FormikSelectField } from '../../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../../components/forms/StepperFormDialog';
import { StaleVersionAlert } from '../../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../../components/lifecycle/useStaleVersion';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { withErrorCode } from '../../shared/errorHints';
import { CURRENCY_OPTIONS } from '../../shared/financeDisplay';
import {
  DEPOSIT_ACCOUNT_ERROR_HINTS,
  DEPOSIT_ACCOUNT_TYPE_LABELS,
  DEPOSIT_ACCOUNT_TYPE_OPTIONS,
  depositAccountSchema,
  EMPTY_DEPOSIT_ACCOUNT,
  toDepositAccountPayload,
  toDepositAccountUpdate,
  valuesFromDepositAccount,
  type DepositAccountValues,
} from './depositAccountForm';

interface DepositAccountDialogProps {
  /** Omitted: create a new account. */
  account?: DepositAccountDto;
  onClose: () => void;
  onSaved: (account: DepositAccountDto) => void;
  /** STALE_VERSION on edit: reload the record (the dialog closes). */
  onReload?: () => void;
}

/** Account → Details → Review; create, or edit with the `version` that was read. Mount only while open. */
export function DepositAccountDialog({
  account,
  onClose,
  onSaved,
  onReload,
}: DepositAccountDialogProps) {
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  const [initialValues] = useState<DepositAccountValues>(() =>
    account === undefined ? EMPTY_DEPOSIT_ACCOUNT : valuesFromDepositAccount(account),
  );
  const editing = account !== undefined;
  const steps: FormStep<DepositAccountValues>[] = [
    {
      label: 'Account',
      fields: ['name', 'account_type', 'currency'],
      render: () => (
        <>
          <FormikTextField
            name="name"
            label="Name"
            required
            helperText="What supervisors pick when they remit, e.g. “CRDB main”."
          />
          <FormikSelectField
            name="account_type"
            label="Type"
            options={DEPOSIT_ACCOUNT_TYPE_OPTIONS}
            required
          />
          <FormikSelectField name="currency" label="Currency" options={CURRENCY_OPTIONS} />
        </>
      ),
    },
    {
      label: 'Details',
      fields: ['institution', 'account_number', 'note'],
      render: () => (
        <>
          <FormikTextField name="institution" label="Bank or operator (optional)" />
          <FormikTextField
            name="account_number"
            label={editing ? 'New account number (optional)' : 'Account number (optional)'}
            helperText={
              editing
                ? `Stored: ${account.account_number_masked ?? 'none'}. Leave empty to keep it. Only the last four characters are kept.`
                : 'Only the last four characters are kept (shown as •••• 4821).'
            }
          />
          <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
        </>
      ),
    },
  ];
  return (
    <StepperFormDialog<DepositAccountValues>
      open
      title={editing ? `Edit ${account.name}` : 'New deposit account'}
      steps={steps}
      initialValues={initialValues}
      validationSchema={depositAccountSchema}
      submitLabel={editing ? 'Save changes' : 'Create account'}
      onClose={onClose}
      renderReview={(v) => (
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
              { label: 'Name', value: v.name.trim() || '—' },
              { label: 'Type', value: DEPOSIT_ACCOUNT_TYPE_LABELS[v.account_type] },
              { label: 'Bank or operator', value: v.institution.trim() || '—' },
              {
                label: 'Account number',
                value:
                  v.account_number.trim() === ''
                    ? (account?.account_number_masked ?? '—')
                    : 'Stored masked (last four characters)',
              },
              { label: 'Currency', value: v.currency || 'Tenant base currency' },
              { label: 'Note', value: v.note.trim() || '—' },
            ]}
          />
          <Box>
            <Alert severity="info">
              Supervisors and the office choose this account when they record a remittance.
            </Alert>
          </Box>
        </Stack>
      )}
      onSubmit={async (v) => {
        try {
          if (account === undefined) {
            const body = toDepositAccountPayload(v);
            onSaved(await depositAccountService.create(body, keyFor(body)));
          } else {
            const body = toDepositAccountUpdate(v, account.version);
            onSaved(
              await guard(() => depositAccountService.update(account.id, body, keyFor(body))),
            );
          }
        } catch (err) {
          throw withErrorCode(err, DEPOSIT_ACCOUNT_ERROR_HINTS);
        }
      }}
    />
  );
}
