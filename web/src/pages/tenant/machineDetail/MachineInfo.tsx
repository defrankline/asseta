import type { AreaDto, CategoryDto, MachineDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { formatInstantIn } from '../../../utils/time';
import { labelOf, MACHINE_STATUS_TONES, OWNERSHIP_OPTIONS } from '../shared/display';

interface MachineInfoProps {
  machine: MachineDto;
  categories: readonly CategoryDto[];
  areas: readonly AreaDto[];
  timeZone: string;
}

const dash = (v: string | null) => (v === null || v === '' ? '—' : v);

/** Registry record of a machine (read-only). */
export function MachineInfo({ machine: m, categories, areas, timeZone }: MachineInfoProps) {
  const category = categories.find((c) => c.id === m.category_id)?.name ?? null;
  const area = areas.find((a) => a.id === m.operating_area_id);
  return (
    <KeyValueGrid
      columns={4}
      items={[
        { label: 'Asset code', value: m.asset_code },
        { label: 'Status', value: <StatusChip status={m.status} tones={MACHINE_STATUS_TONES} /> },
        { label: 'Category', value: dash(category) },
        {
          label: 'Operating area',
          value: area === undefined ? '—' : `${area.code} · ${area.name}`,
        },
        { label: 'Manufacturer', value: dash(m.manufacturer) },
        { label: 'Model', value: dash(m.model) },
        { label: 'Serial number', value: dash(m.serial_number) },
        {
          label: 'Year',
          value: m.year_of_manufacture === null ? '—' : String(m.year_of_manufacture),
        },
        {
          label: 'Capacity',
          value:
            m.capacity_value === null ? '—' : `${m.capacity_value} ${m.capacity_unit ?? ''}`.trim(),
        },
        { label: 'Meter decimal places', value: String(m.meter_decimal_places) },
        { label: 'Ownership', value: labelOf(OWNERSHIP_OPTIONS, m.ownership) },
        { label: 'Registered', value: formatInstantIn(m.created_at, timeZone) },
      ]}
    />
  );
}
