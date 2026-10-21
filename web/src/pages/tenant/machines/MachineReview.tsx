import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MACHINE_STATUS_OPTIONS, OWNERSHIP_OPTIONS, labelOf } from '../shared/display';
import type { MachineFormValues } from './machineForm';
import type { MachineLookups } from './useMachineLookups';

const dash = (v: string) => (v.trim() === '' ? '—' : v.trim());

export function MachineReview({
  values: v,
  lookups,
  mode,
}: {
  values: MachineFormValues;
  lookups: MachineLookups;
  mode: 'create' | 'edit';
}) {
  const category = lookups.categories.find((c) => c.id === v.category_id)?.name ?? '—';
  const area = lookups.areas.find((a) => a.id === v.operating_area_id)?.name ?? '—';
  return (
    <KeyValueGrid
      items={[
        { label: 'Asset code', value: dash(v.asset_code) },
        { label: 'Name', value: dash(v.name) },
        ...(mode === 'edit'
          ? [{ label: 'Status', value: labelOf(MACHINE_STATUS_OPTIONS, v.status) }]
          : []),
        { label: 'Manufacturer', value: dash(v.manufacturer) },
        { label: 'Model', value: dash(v.model) },
        { label: 'Serial number', value: dash(v.serial_number) },
        { label: 'Year', value: dash(v.year_of_manufacture) },
        { label: 'Category', value: category },
        { label: 'Operating area', value: area },
        { label: 'Ownership', value: labelOf(OWNERSHIP_OPTIONS, v.ownership) },
        { label: 'Meter decimal places', value: v.meter_decimal_places },
        {
          label: 'Capacity',
          value: v.capacity_value.trim() === '' ? '—' : `${v.capacity_value} ${v.capacity_unit}`,
        },
      ]}
    />
  );
}
