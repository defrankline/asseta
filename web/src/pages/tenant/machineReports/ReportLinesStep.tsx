import { Alert, Box, Button, Stack, Typography } from '@mui/material';
import { useFormikContext } from 'formik';
import { useCallback } from 'react';
import type { AvailableHoursDto, MachineReportReasonDto } from '../../../api/machineReportTypes';
import { machineReportService } from '../../../api/services/machineReportService';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { compareDecimal } from '../../../utils/money';
import { hoursLabel, minus, plainHours } from './machineReportDisplay';
import {
  accountedFor,
  balanceText,
  customerTotal,
  emptyLine,
  meterDifference,
  type ReportRules,
  type ReportValues,
} from './reportForm';

const decimal = { htmlInput: { inputMode: 'decimal' as const } };
const MAX_LINES = 50;

const matches = (text: string, query: string) =>
  text.toLowerCase().includes(query.trim().toLowerCase());

const customerLabel = (c: AvailableHoursDto) =>
  `${c.customer_name ?? c.customer_id} · available ${hoursLabel(c.available)}`;

interface LinesStepProps {
  machineId: string;
  rules: ReportRules;
  /** Customers known when the form opened (context, plus the rejected report's customers). */
  customers: readonly AvailableHoursDto[];
  reasons: readonly MachineReportReasonDto[];
  hoursOn: boolean;
}

/** Account for hours: customer lines (from hours they bought) and non-productive lines. */
export function ReportLinesStep({ machineId, rules, customers, reasons, hoursOn }: LinesStepProps) {
  const { values, setFieldValue, errors } = useFormikContext<ReportValues>();
  const difference = meterDifference(rules, values.reading);
  const accounted = accountedFor(values.lines);
  const searchCustomers = useCallback(
    async (query: string, signal: AbortSignal) =>
      (await machineReportService.availableHours({ machine_id: machineId }, signal)).filter(
        (c) => compareDecimal(c.available, '0') > 0 && matches(c.customer_name ?? '', query),
      ),
    [machineId],
  );
  const resolveCustomer = useCallback(
    (id: string) => Promise.resolve(customers.find((c) => c.customer_id === id) ?? null),
    [customers],
  );
  const searchReasons = useCallback(
    (query: string) =>
      Promise.resolve(reasons.filter((r) => r.is_active && matches(`${r.name} ${r.code}`, query))),
    [reasons],
  );
  const resolveReason = useCallback(
    (id: string) => Promise.resolve(reasons.find((r) => r.id === id) ?? null),
    [reasons],
  );
  const add = (kind: 'CUSTOMER' | 'NON_PRODUCTIVE') => {
    const left = difference === null ? '' : minus(difference, accounted);
    const hours = left !== '' && compareDecimal(left, '0') > 0 ? plainHours(left) : '';
    void setFieldValue('lines', [...values.lines, emptyLine(kind, hours)]);
  };
  const balance = difference === null ? null : balanceText(difference, accounted);
  const linesError = typeof errors.lines === 'string' ? errors.lines : null;
  return (
    <>
      <Box role="status" aria-live="polite">
        <Typography variant="h6" component="p">
          Accounted for {hoursLabel(accounted)}
          {difference !== null && ` / ${hoursLabel(difference)}`}
        </Typography>
        <Typography variant="body2" color={balance === null ? 'success.main' : 'text.secondary'}>
          {balance ?? 'Every hour is accounted for.'}
        </Typography>
      </Box>
      {values.lines.map((line, i) => {
        const at = (f: string) => `lines[${i}].${f}`;
        const available = rules.available[line.customer_id];
        return (
          <Stack
            key={line.key}
            spacing={1.5}
            sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5 }}
          >
            <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography variant="subtitle2">
                {line.kind === 'CUSTOMER' ? 'Customer' : 'Non-productive'} · line {i + 1}
              </Typography>
              <Button
                size="small"
                color="inherit"
                aria-label={`Remove line ${i + 1}`}
                onClick={() => {
                  void setFieldValue(
                    'lines',
                    values.lines.filter((_, j) => j !== i),
                  );
                }}
              >
                Remove
              </Button>
            </Stack>
            {line.kind === 'CUSTOMER' ? (
              <FormikAsyncIdAutocomplete<AvailableHoursDto>
                name={at('customer_id')}
                label="Customer"
                required
                fetchOptions={searchCustomers}
                resolveOption={resolveCustomer}
                getOptionId={(c) => c.customer_id}
                getOptionLabel={customerLabel}
                noOptionsText="No customer has usable hours for this machine"
              />
            ) : (
              <FormikAsyncIdAutocomplete<MachineReportReasonDto>
                name={at('reason_id')}
                label="Reason"
                required
                fetchOptions={searchReasons}
                resolveOption={resolveReason}
                getOptionId={(r) => r.id}
                getOptionLabel={(r) => r.name}
                noOptionsText="No reason matches"
              />
            )}
            <FormikTextField name={at('hours')} label="Hours" required slotProps={decimal} />
            {line.kind === 'CUSTOMER' && line.customer_id !== '' && available !== undefined && (
              <Typography variant="body2" color="text.secondary">
                Available {hoursLabel(available)} · after this{' '}
                {hoursLabel(minus(available, customerTotal(values.lines, line.customer_id)))}
              </Typography>
            )}
            {line.kind === 'NON_PRODUCTIVE' && (
              <FormikTextField
                name={at('note')}
                label="What happened"
                required
                multiline
                minRows={2}
              />
            )}
          </Stack>
        );
      })}
      {values.lines.length < MAX_LINES && (
        <Box className="flex flex-wrap gap-2">
          {hoursOn && (
            <Button
              variant="outlined"
              onClick={() => {
                add('CUSTOMER');
              }}
            >
              Add customer
            </Button>
          )}
          <Button
            variant="outlined"
            onClick={() => {
              add('NON_PRODUCTIVE');
            }}
          >
            Add non-productive
          </Button>
        </Box>
      )}
      {linesError !== null && linesError !== balance && (
        <Alert severity="error">{linesError}</Alert>
      )}
      <Typography variant="body2" color="text.secondary">
        A customer can only get hours they have bought and that are usable. Non-productive hours
        need a reason and a note.
      </Typography>
      <FormikTextField name="note" label="Note for the approver (optional)" multiline minRows={2} />
    </>
  );
}
