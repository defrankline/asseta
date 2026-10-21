import Add from '@mui/icons-material/Add';
import { Alert, Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { CanMutate } from '../../../access/CanMutate';
import { newUuid } from '../../../api/ids';
import { fuelService } from '../../../api/services/expenseService';
import type { FuelEventDto, MachineDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { FormikDateTimeField } from '../../../components/forms/FormikDateTimeField';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { StepperFormDialog } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { labelOf } from '../shared/display';
import { withErrorCode } from '../shared/errorHints';
import {
  CURRENCY_OPTIONS,
  FINANCE_ERROR_HINTS,
  FUEL_EVENT_OPTIONS,
} from '../shared/financeDisplay';
import {
  FormikExpenseIdPicker,
  FormikJobIdPicker,
  FormikMachineIdPicker,
  MachineFilter,
} from '../shared/financePickers';
import { useMachineLabels } from '../shared/useMachineLabels';
import { emptyFuelValues, fuelFormSchema, toFuelPayload, type FuelFormValues } from './expenseForm';

function RecordFuelDialog({
  timeZone,
  onClose,
  onRecorded,
}: {
  timeZone: string;
  onClose: () => void;
  onRecorded: (e: FuelEventDto) => void;
}) {
  const keyFor = useIdempotencyKey();
  const [clientId] = useState(() => newUuid());
  const [initial] = useState(() => emptyFuelValues(new Date().toISOString()));
  return (
    <StepperFormDialog<FuelFormValues>
      open
      title="Record fuel event"
      initialValues={initial}
      validationSchema={fuelFormSchema}
      submitLabel="Record fuel event"
      onClose={onClose}
      steps={[
        {
          label: 'Fuel',
          fields: ['event_type', 'litres', 'unit_price', 'currency', 'occurred_at'],
          render: (f) => (
            <>
              <FormikSelectField
                name="event_type"
                label="Type"
                options={FUEL_EVENT_OPTIONS}
                required
              />
              <FormikTextField name="litres" label="Litres" required />
              {f.values.event_type !== 'USAGE' && (
                <>
                  <FormikTextField
                    name="unit_price"
                    label="Unit price (optional)"
                    helperText="Cost = litres × unit price, computed by the server."
                  />
                  <FormikSelectField name="currency" label="Currency" options={CURRENCY_OPTIONS} />
                </>
              )}
              <FormikDateTimeField
                name="occurred_at"
                label="Occurred at"
                timeZone={timeZone}
                required
              />
            </>
          ),
        },
        {
          label: 'Attribution',
          fields: ['machine_id', 'job_id', 'expense_id', 'meter_reading', 'supplier', 'note'],
          render: (f) => (
            <>
              <FormikMachineIdPicker name="machine_id" label="Machine (optional)" />
              <FormikJobIdPicker name="job_id" label="Job (optional)" />
              {f.values.event_type === 'PURCHASE' && (
                <FormikExpenseIdPicker
                  name="expense_id"
                  label="Paying expense (optional)"
                  helperText="Links the purchase to the expense that paid it so the cost is not counted twice."
                />
              )}
              <FormikTextField name="meter_reading" label="Meter reading (optional)" />
              <FormikTextField name="supplier" label="Supplier (optional)" />
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
              { label: 'Type', value: labelOf(FUEL_EVENT_OPTIONS, v.event_type) },
              { label: 'Litres', value: v.litres },
              { label: 'Unit price', value: v.unit_price || '—' },
              { label: 'Occurred at', value: formatInstantIn(v.occurred_at, timeZone) },
            ]}
          />
          <Alert severity="info">Fuel events are a log: they are not edited after recording.</Alert>
        </>
      )}
      onSubmit={async (v) => {
        const body = toFuelPayload(v, clientId);
        try {
          onRecorded(await fuelService.record(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, FINANCE_ERROR_HINTS);
        }
      }}
    />
  );
}

/** Fuel purchase / issue / usage log with server-attributed cost. */
export function FuelTab({ timeZone }: { timeZone: string }) {
  const notify = useNotify();
  const machineLabel = useMachineLabels();
  const [type, setType] = useState('');
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [recording, setRecording] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<FuelEventDto>>(
    (query, signal) => fuelService.list(query, signal),
    [],
  );
  const columns: DataColumn<FuelEventDto>[] = [
    { id: 'at', header: 'Occurred', render: (f) => formatInstantIn(f.occurred_at, timeZone) },
    { id: 'type', header: 'Type', render: (f) => labelOf(FUEL_EVENT_OPTIONS, f.event_type) },
    { id: 'litres', header: 'Litres', align: 'right', render: (f) => f.litres },
    {
      id: 'machine',
      header: 'Machine',
      render: (f) => (f.machine_id === null ? '—' : machineLabel(f.machine_id)),
    },
    { id: 'supplier', header: 'Supplier', render: (f) => f.supplier ?? '—' },
    { id: 'meter', header: 'Meter', render: (f) => f.meter_reading ?? '—' },
    {
      id: 'cost',
      header: 'Attributed cost',
      align: 'right',
      render: (f) => <MoneyText amount={f.attributed_cost} currency={f.currency} />,
    },
  ];
  return (
    <>
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(f) => f.id}
        searchable={false}
        reloadKey={reloadKey}
        filters={{ event_type: type || undefined, machine_id: machine?.id }}
        emptyTitle="No fuel events"
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="Type"
              value={type}
              options={FUEL_EVENT_OPTIONS}
              onChange={setType}
            />
            <Box sx={{ minWidth: 220 }}>
              <MachineFilter label="Machine" value={machine} onChange={setMachine} />
            </Box>
            <Box className="flex-1" />
            <CanMutate permission={PERMISSIONS.tenantExpenseWrite}>
              <Button
                variant="contained"
                startIcon={<Add />}
                onClick={() => {
                  setRecording(true);
                }}
              >
                Record fuel
              </Button>
            </CanMutate>
          </Box>
        }
      />
      {recording && (
        <RecordFuelDialog
          timeZone={timeZone}
          onClose={() => {
            setRecording(false);
          }}
          onRecorded={() => {
            notify.success('Fuel event recorded.');
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
