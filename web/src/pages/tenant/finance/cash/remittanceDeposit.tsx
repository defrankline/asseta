import { Alert, Box, Chip, Typography } from '@mui/material';
import { useField, useFormikContext } from 'formik';
import { useCallback, useEffect } from 'react';
import type { DepositAccountDto } from '../../../../api/custodyTypes';
import { newIdempotencyKey } from '../../../../api/ids';
import { cashService } from '../../../../api/services/cashService';
import type { AttachmentDto, CashHandoverDto } from '../../../../api/types';
import { FormikSelectField } from '../../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { AttachmentPhoto } from '../../../../components/meter/AttachmentPhoto';
import { AttachmentUpload } from '../../../../components/meter/AttachmentUpload';
import { FormikDepositAccountIdPicker } from '../depositAccounts/depositAccountPickers';
import {
  MAX_REMITTANCE_EVIDENCE,
  METHOD_ACCOUNT_TYPE,
  needsReference,
  REMITTANCE_METHOD_LABELS,
  REMITTANCE_METHOD_OPTIONS,
  type HandoverValues,
  type RemittanceRequirements,
} from './cashForms';
import { requirementLines } from './remittanceDetails';

interface DepositFieldsProps {
  requirements: RemittanceRequirements;
  onAccountChange: (account: DepositAccountDto | null) => void;
  account: DepositAccountDto | null;
}

/** Method → company account → reference → evidence photos (uploaded immediately). */
export function RemittanceDepositFields({
  requirements: req,
  onAccountChange,
  account,
}: DepositFieldsProps) {
  const { values, setFieldValue } = useFormikContext<HandoverValues>();
  const [, evidenceMeta] = useField<AttachmentDto[]>('evidence');
  const accountType = METHOD_ACCOUNT_TYPE[values.method];
  // A method change never leaves an account of another type selected.
  useEffect(() => {
    if (account !== null && account.account_type !== accountType) {
      void setFieldValue('deposit_account_id', '');
      onAccountChange(null);
    }
  }, [account, accountType, setFieldValue, onAccountChange]);
  const referenceRequired = req.reference && needsReference(values.method);
  const lines = requirementLines(req);
  const upload = (file: File) => cashService.uploadRemittanceEvidence(file, newIdempotencyKey());
  const evidenceError =
    evidenceMeta.touched && typeof evidenceMeta.error === 'string' ? evidenceMeta.error : null;
  return (
    <>
      {lines.length > 0 && (
        <Alert severity="info">Your organisation requires {lines.join('; ')}.</Alert>
      )}
      <FormikSelectField
        name="method"
        label="How was it paid?"
        options={REMITTANCE_METHOD_OPTIONS}
        required
      />
      <FormikDepositAccountIdPicker
        name="deposit_account_id"
        label={req.account ? 'Company account' : 'Company account (optional)'}
        accountType={accountType}
        currency={values.currency}
        required={req.account}
        onOptionChange={(a) => {
          onAccountChange(a);
          if (a !== null && values.currency !== a.currency) {
            void setFieldValue('currency', a.currency);
          }
        }}
        helperText={`${REMITTANCE_METHOD_LABELS[values.method]}: only active accounts of that kind are listed.`}
      />
      <FormikTextField
        name="reference"
        label={
          referenceRequired
            ? 'Transaction reference'
            : needsReference(values.method)
              ? 'Transaction reference (optional)'
              : 'Reference (optional)'
        }
        required={referenceRequired}
        helperText={
          needsReference(values.method)
            ? 'From the deposit slip or the payment message.'
            : 'Cash handed to the office needs no reference.'
        }
      />
      <Box className="flex flex-col gap-1">
        <Typography variant="body2">
          {req.evidence
            ? 'Photo of the deposit slip or payment confirmation (required)'
            : 'Photo of the deposit slip or payment confirmation (optional)'}
        </Typography>
        <Box className="flex flex-wrap gap-1">
          {values.evidence.map((a, i) => (
            <Chip
              key={a.id}
              label={`Photo ${String(i + 1)}`}
              onDelete={() => {
                void setFieldValue(
                  'evidence',
                  values.evidence.filter((x) => x.id !== a.id),
                );
              }}
            />
          ))}
        </Box>
        <AttachmentUpload
          label="Add photo"
          value={null}
          onChange={(a) => {
            if (a !== null) void setFieldValue('evidence', [...values.evidence, a]);
          }}
          upload={upload}
          accept="image/*,application/pdf"
          capture="environment"
          helperText={`Up to ${String(MAX_REMITTANCE_EVIDENCE)} photos; originals are stored unchanged.`}
          disabled={values.evidence.length >= MAX_REMITTANCE_EVIDENCE}
        />
        {evidenceError !== null && <Alert severity="error">{evidenceError}</Alert>}
      </Box>
    </>
  );
}

/** The remittance's evidence photos, each fetched as a short-lived URL on demand. */
export function RemittanceEvidence({ handover: h }: { handover: CashHandoverDto }) {
  const ids = h.evidence_attachment_ids ?? [];
  const fetchUrl = useCallback(
    (attachmentId: string) => cashService.remittanceEvidenceUrl(h.id, attachmentId),
    [h.id],
  );
  if (ids.length === 0) return <>No photo</>;
  return (
    <Box className="flex flex-wrap gap-2">
      {ids.map((id, i) => (
        <AttachmentPhoto
          key={id}
          attachmentId={id}
          fetchUrl={fetchUrl}
          label={`View photo ${String(i + 1)}`}
        />
      ))}
    </Box>
  );
}
