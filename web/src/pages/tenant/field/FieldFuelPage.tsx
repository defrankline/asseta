import Add from '@mui/icons-material/Add';
import { Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { CanMutate } from '../../../access/CanMutate';
import { fuelService } from '../../../api/services/expenseService';
import type { FuelEventDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { MoneyText } from '../../../components/display/MoneyText';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { RecordFuelDialog } from '../expenses/FuelTab';
import { labelOf } from '../shared/display';
import { FUEL_EVENT_OPTIONS } from '../shared/financeDisplay';
import { useFieldJobLabels, useFieldMachineLabels } from './fieldLookups';

/** The caller's fuel log (issues to machines, purchases, usage) and recording a new event. */
export function FieldFuelPage() {
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const jobLabel = useFieldJobLabels();
  const machineLabel = useFieldMachineLabels();
  const [type, setType] = useState('');
  const [recording, setRecording] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<FuelEventDto>>(
    (query, signal) =>
      fuelService.list({ ...query, filters: { ...query.filters, mine: 'true' } }, signal),
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
    { id: 'job', header: 'Job', render: (f) => (f.job_id === null ? '—' : jobLabel(f.job_id)) },
    { id: 'meter', header: 'Meter', render: (f) => f.meter_reading ?? '—' },
    {
      id: 'price',
      header: 'Unit price',
      align: 'right',
      render: (f) =>
        f.unit_price === null ? '—' : <MoneyText amount={f.unit_price} currency={f.currency} />,
    },
    {
      id: 'cost',
      header: 'Cost',
      align: 'right',
      render: (f) => <MoneyText amount={f.attributed_cost} currency={f.currency} />,
    },
  ];
  return (
    <>
      <PageHeader
        title="Fuel"
        subtitle="Fuel you issued to machines, bought or used; the server attributes the cost"
      />
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(f) => f.id}
        searchable={false}
        reloadKey={reloadKey}
        filters={{ event_type: type || undefined }}
        emptyTitle="No fuel recorded"
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="Type"
              value={type}
              options={FUEL_EVENT_OPTIONS}
              onChange={setType}
            />
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
          variant="field"
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
