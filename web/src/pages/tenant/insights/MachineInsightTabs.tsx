import { Alert, Box, Typography } from '@mui/material';
import type { FuelEfficiencyInsightDto, UtilisationInsightDto } from '../../../api/types';
import { MiniBars } from '../../../components/charts/MiniBars';
import { RangeMarker } from '../../../components/charts/RangeMarker';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { StatusChip } from '../../../components/display/StatusChip';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { formatInstantIn } from '../../../utils/time';
import {
  formatNumber,
  insufficientText,
  TREND_LABELS,
  TREND_TONES,
  weekEndingLabel,
} from './insightsDisplay';

const machineCell = (m: { asset_code: string; machine_name: string }) =>
  `${m.asset_code} · ${m.machine_name}`;

const FUEL_TONES = { OUTSIDE: 'warning', WITHIN: 'success', INSUFFICIENT: 'default' } as const;
const FUEL_LABELS = {
  OUTSIDE: 'Outside usual range',
  WITHIN: 'Within usual range',
  INSUFFICIENT: 'Not enough history',
} as const;

function fuelState(f: FuelEfficiencyInsightDto): keyof typeof FUEL_LABELS {
  if (f.status === 'INSUFFICIENT_DATA') return 'INSUFFICIENT';
  return f.outside_usual_range === true ? 'OUTSIDE' : 'WITHIN';
}

function Notes({ item }: { item: FuelEfficiencyInsightDto | UtilisationInsightDto }) {
  return (
    <Typography variant="body2" color="text.secondary">
      {item.status === 'INSUFFICIENT_DATA' ? insufficientText(item) : item.message}
    </Typography>
  );
}

/** Litres per meter hour this week vs the machine's own usual band. */
export function FuelEfficiencyTab({
  items,
  timeZone,
}: {
  items: readonly FuelEfficiencyInsightDto[];
  timeZone: string;
}) {
  if (items.length === 0) return <EmptyState title="No machines to compare yet" />;
  const flagged = items.filter((f) => fuelState(f) === 'OUTSIDE').length;
  const insufficient = items.filter((f) => f.status === 'INSUFFICIENT_DATA').length;
  const columns: DataColumn<FuelEfficiencyInsightDto>[] = [
    { id: 'machine', header: 'Machine', render: machineCell },
    {
      id: 'week',
      header: 'Week ending',
      render: (f) => formatInstantIn(f.week_ending, timeZone),
    },
    {
      id: 'current',
      header: 'Litres per meter hour',
      align: 'right',
      render: (f) => formatNumber(f.current_litres_per_hour, 2),
    },
    {
      id: 'band',
      header: 'Usual range',
      render: (f) =>
        f.band_low === null || f.band_high === null
          ? '—'
          : `${formatNumber(f.band_low, 2)} – ${formatNumber(f.band_high, 2)} (median ${formatNumber(
              f.median_litres_per_hour,
              2,
            )})`,
    },
    {
      id: 'chart',
      header: 'Compared',
      render: (f) =>
        f.current_litres_per_hour === null || f.band_low === null || f.band_high === null ? (
          '—'
        ) : (
          <RangeMarker
            value={f.current_litres_per_hour}
            low={f.band_low}
            high={f.band_high}
            median={f.median_litres_per_hour}
            label={`${formatNumber(f.current_litres_per_hour, 2)} litres per meter hour; usual range ${formatNumber(
              f.band_low,
              2,
            )} to ${formatNumber(f.band_high, 2)}`}
          />
        ),
    },
    {
      id: 'status',
      header: 'Status',
      render: (f) => (
        <StatusChip status={fuelState(f)} tones={FUEL_TONES} label={FUEL_LABELS[fuelState(f)]} />
      ),
    },
    { id: 'notes', header: 'Notes', render: (f) => <Notes item={f} /> },
  ];
  return (
    <Box className="flex flex-col gap-3">
      <Typography variant="body2" color="text.secondary">
        {flagged} of {items.length} machines outside their usual range this week
        {insufficient > 0 ? `; ${String(insufficient)} without enough history yet` : ''}.
      </Typography>
      <StaticTable
        ariaLabel="Fuel efficiency per machine"
        columns={columns}
        rows={items}
        getRowId={(f) => f.machine_id}
        isRowMuted={(f) => f.status === 'INSUFFICIENT_DATA'}
      />
    </Box>
  );
}

/** Hours per available day and the weekly trend per machine. */
export function UtilisationTab({
  items,
  timeZone,
}: {
  items: readonly UtilisationInsightDto[];
  timeZone: string;
}) {
  if (items.length === 0) return <EmptyState title="No machines to compare yet" />;
  const columns: DataColumn<UtilisationInsightDto>[] = [
    { id: 'machine', header: 'Machine', render: machineCell },
    {
      id: 'perDay',
      header: 'Hours per available day',
      align: 'right',
      render: (u) => formatNumber(u.hours_per_available_day, 1),
    },
    { id: 'days', header: 'Available days', align: 'right', render: (u) => u.available_days },
    {
      id: 'weekly',
      header: 'Weekly hours',
      render: (u) => (
        <MiniBars
          label={`Weekly hours for ${u.asset_code}, ${String(u.weekly.length)} weeks`}
          bars={u.weekly.map((w) => ({
            key: w.week_ending,
            value: w.hours,
            title: `${weekEndingLabel(w.week_ending, timeZone)}: ${formatNumber(w.hours, 1)} h`,
          }))}
        />
      ),
    },
    {
      id: 'trend',
      header: 'Trend',
      render: (u) =>
        u.trend === null ? (
          '—'
        ) : (
          <Box className="flex items-center gap-2">
            <StatusChip status={u.trend} tones={TREND_TONES} label={TREND_LABELS[u.trend]} />
            <Typography variant="caption" color="text.secondary">
              {u.trend_hours_per_week === null
                ? ''
                : `${u.trend_hours_per_week > 0 ? '+' : ''}${formatNumber(u.trend_hours_per_week, 1)} h/week`}
            </Typography>
          </Box>
        ),
    },
    { id: 'notes', header: 'Notes', render: (u) => <Notes item={u} /> },
  ];
  const insufficient = items.filter((u) => u.status === 'INSUFFICIENT_DATA').length;
  return (
    <Box className="flex flex-col gap-3">
      {insufficient > 0 && (
        <Alert severity="info">
          {insufficient} of {items.length} machines do not have enough observed weeks yet; their
          rows explain what is missing.
        </Alert>
      )}
      <StaticTable
        ariaLabel="Utilisation per machine"
        columns={columns}
        rows={items}
        getRowId={(u) => u.machine_id}
        isRowMuted={(u) => u.status === 'INSUFFICIENT_DATA'}
      />
    </Box>
  );
}
