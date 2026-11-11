import { Alert } from '@mui/material';
import { useField, useFormikContext } from 'formik';
import { useCallback } from 'react';
import type { PettyCashAdvanceDto, PettyCashFundDto } from '../../../../api/pettyCashTypes';
import { peopleService } from '../../../../api/services/peopleService';
import { pettyCashService } from '../../../../api/services/pettyCashService';
import type { AttachmentDto, PersonDto } from '../../../../api/types';
import { AsyncAutocomplete } from '../../../../components/data/AsyncAutocomplete';
import { FormikAsyncIdAutocomplete } from '../../../../components/forms/FormikAsyncIdAutocomplete';
import { EvidenceUpload } from '../../engineHours/allocations/EvidenceUpload';
import { fundLabel, searchFunds } from './pettyCashState';

const searchAnyFund = (q: string, signal: AbortSignal) => searchFunds(q, signal, true);
const resolveFund = (id: string, signal: AbortSignal) => pettyCashService.fund(id, signal);

interface IdPickerProps<T> {
  name: string;
  label: string;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
  onOptionChange?: (option: T | null) => void;
}

/** Active petty cash funds (server search), bound to a Formik id field. */
export function FormikFundIdPicker(props: IdPickerProps<PettyCashFundDto>) {
  return (
    <FormikAsyncIdAutocomplete<PettyCashFundDto>
      {...props}
      fetchOptions={searchFunds}
      resolveOption={resolveFund}
      getOptionId={(f) => f.id}
      getOptionLabel={fundLabel}
      noOptionsText="No active fund matches"
    />
  );
}

/** List filter: one fund (server search; inactive funds included). */
export function FundFilter({
  value,
  onChange,
  label = 'Fund',
}: {
  value: PettyCashFundDto | null;
  onChange: (value: PettyCashFundDto | null) => void;
  label?: string;
}) {
  return (
    <AsyncAutocomplete<PettyCashFundDto>
      label={label}
      size="small"
      placeholder="All funds"
      value={value}
      onChange={onChange}
      fetchOptions={searchAnyFund}
      getOptionLabel={fundLabel}
      isOptionEqualToValue={(a, b) => a.id === b.id}
    />
  );
}

/** Advances of one fund that are not cleared yet (server search), bound to a Formik id field. */
export function FormikAdvanceIdPicker({
  fundId,
  ...props
}: IdPickerProps<PettyCashAdvanceDto> & { fundId: string }) {
  const fetchOptions = useCallback(
    async (q: string, signal: AbortSignal) =>
      fundId === ''
        ? []
        : (
            await pettyCashService.advances(
              { page: 1, page_size: 20, q, filters: { fund_id: fundId, status: 'OUTSTANDING' } },
              signal,
            )
          ).items,
    [fundId],
  );
  const resolveOption = useCallback(
    (id: string, signal: AbortSignal) => pettyCashService.advance(id, signal),
    [],
  );
  return (
    <FormikAsyncIdAutocomplete<PettyCashAdvanceDto>
      {...props}
      fetchOptions={fetchOptions}
      resolveOption={resolveOption}
      getOptionId={(a) => a.id}
      getOptionLabel={(a) => `${a.number} · ${a.purpose}`}
      noOptionsText="No advance of this fund is waiting to be cleared"
    />
  );
}

const searchPeople = (q: string, signal: AbortSignal) => peopleService.search(q, signal);
const resolvePerson = async (id: string, signal: AbortSignal) =>
  (await peopleService.list([id], signal))[0] ?? null;

/** A colleague's login (server search by name), e.g. a count witness. */
export function FormikPersonIdPicker(props: IdPickerProps<PersonDto>) {
  return (
    <FormikAsyncIdAutocomplete<PersonDto>
      {...props}
      fetchOptions={searchPeople}
      resolveOption={resolvePerson}
      getOptionId={(p) => p.user_id}
      getOptionLabel={(p) => p.display_name}
    />
  );
}

/** Evidence photos (slip, cash, count sheet) uploaded to the petty cash evidence store. */
export function FormikPettyEvidenceField({
  name = 'evidence',
  label = 'Evidence (photos)',
  required = false,
}: {
  name?: string;
  label?: string;
  required?: boolean;
}) {
  const [field, meta, helpers] = useField<AttachmentDto[]>(name);
  const { submitCount } = useFormikContext();
  return (
    <>
      <EvidenceUpload
        value={field.value}
        onChange={(next) => {
          void helpers.setValue(next);
        }}
        upload={(file, key) => pettyCashService.uploadEvidence(file, key)}
        label={label}
        required={required}
        helperText={
          required
            ? 'Required by your company policy: a photo of the slip, the cash or the count sheet.'
            : 'Optional: a photo of the slip, the cash or the count sheet.'
        }
      />
      {(meta.touched || submitCount > 0) && typeof meta.error === 'string' && (
        <Alert severity="error">{meta.error}</Alert>
      )}
    </>
  );
}
