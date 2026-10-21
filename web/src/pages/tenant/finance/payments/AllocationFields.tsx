import Add from '@mui/icons-material/Add';
import Clear from '@mui/icons-material/Clear';
import { Alert, Box, Button, IconButton, Typography } from '@mui/material';
import { FieldArray, getIn, useFormikContext } from 'formik';
import { useMemo } from 'react';
import type { HireInvoiceDto } from '../../../../api/types';
import { AsyncAutocomplete } from '../../../../components/data/AsyncAutocomplete';
import { MoneyText } from '../../../../components/display/MoneyText';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { invoiceOptionLabel, searchIssuedInvoices } from '../../shared/financeLookups';
import type { AllocationRow } from './paymentForm';

interface Values {
  customer_id: string;
  currency: string;
  allocations: AllocationRow[];
}

const sameId = (a: { id: string }, b: { id: string }) => a.id === b.id;

/**
 * Allocate a payment to the customer's issued invoices (partial amounts allowed). Whatever is not
 * allocated stays on the customer's account as credit (deposit / advance) once verified.
 */
export function AllocationFields({ intro }: { intro?: string }) {
  const { values, errors, touched, setFieldValue } = useFormikContext<Values>();
  const fetchOptions = useMemo(
    () => searchIssuedInvoices(values.customer_id),
    [values.customer_id],
  );
  const listError = getIn(errors, 'allocations') as unknown;
  const showListError =
    typeof listError === 'string' && getIn(touched, 'allocations') !== undefined;
  return (
    <FieldArray name="allocations">
      {(helpers) => (
        <Box className="flex flex-col gap-3">
          <Typography variant="body2" color="text.secondary">
            {intro ??
              'Optional. Unallocated money becomes customer credit (deposit / advance) once verified; it can be allocated later.'}
          </Typography>
          {values.allocations.map((row, i) => (
            <Box key={i} className="flex flex-wrap items-start gap-2">
              <Box sx={{ flex: '2 1 280px' }}>
                <AsyncAutocomplete<HireInvoiceDto>
                  label={`Invoice ${String(i + 1)}`}
                  value={row.invoice}
                  fetchOptions={fetchOptions}
                  getOptionLabel={invoiceOptionLabel}
                  isOptionEqualToValue={sameId}
                  noOptionsText="No issued invoice of this customer matches"
                  error={
                    getIn(touched, `allocations.${String(i)}.invoice`) !== undefined
                      ? (getIn(errors, `allocations.${String(i)}.invoice`) as string | undefined)
                      : undefined
                  }
                  onChange={(inv) => {
                    void setFieldValue(`allocations.${String(i)}.invoice`, inv);
                    if (inv !== null && values.currency === '') {
                      void setFieldValue('currency', inv.currency);
                    }
                  }}
                />
                {row.invoice !== null && (
                  <Typography variant="caption" color="text.secondary">
                    Open (verified) balance:{' '}
                    <MoneyText amount={row.invoice.balance} currency={row.invoice.currency} />
                  </Typography>
                )}
              </Box>
              <Box sx={{ flex: '1 1 160px' }}>
                <FormikTextField
                  name={`allocations.${String(i)}.amount`}
                  label="Amount"
                  required
                  slotProps={{ htmlInput: { inputMode: 'decimal' } }}
                />
              </Box>
              <IconButton
                aria-label={`Remove allocation ${String(i + 1)}`}
                onClick={() => {
                  helpers.remove(i);
                }}
              >
                <Clear />
              </IconButton>
            </Box>
          ))}
          {showListError && <Alert severity="error">{listError}</Alert>}
          <Box>
            <Button
              size="small"
              startIcon={<Add />}
              disabled={values.customer_id === ''}
              onClick={() => {
                helpers.push({ invoice: null, amount: '' } satisfies AllocationRow);
              }}
            >
              Allocate to an invoice
            </Button>
          </Box>
        </Box>
      )}
    </FieldArray>
  );
}
