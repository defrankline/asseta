import { Box, Chip, Typography } from '@mui/material';
import type { AuditEventDto } from '../../api/types';
import { StaticTable } from '../../components/data/StaticTable';
import type { DataColumn } from '../../components/data/ServerDataTable';
import { KeyValueGrid } from '../../components/display/KeyValueGrid';
import { humanize } from '../../utils/text';
import { diffRows, type DiffRow } from './auditDisplay';

const KIND_LABEL: Readonly<Record<DiffRow['kind'], string | null>> = {
  changed: 'Changed',
  added: 'Added',
  removed: 'Removed',
  unchanged: null,
};

const valueCell = { whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' } as const;

function columns(event: AuditEventDto): DataColumn<DiffRow>[] {
  const cols: DataColumn<DiffRow>[] = [
    {
      id: 'field',
      header: 'Field',
      render: (r) => (
        <Box className="flex flex-wrap items-center gap-1">
          <span>{r.label}</span>
          {KIND_LABEL[r.kind] !== null && (
            <Chip size="small" variant="outlined" label={KIND_LABEL[r.kind]} />
          )}
        </Box>
      ),
    },
  ];
  if (event.before !== null) {
    cols.push({
      id: 'before',
      header: 'Before',
      render: (r) => <Box sx={valueCell}>{r.before}</Box>,
    });
  }
  if (event.after !== null) {
    cols.push({
      id: 'after',
      header: event.before === null ? 'Details' : 'After',
      render: (r) => (
        <Box sx={{ ...valueCell, fontWeight: r.changed ? 600 : 'inherit' }}>{r.after}</Box>
      ),
    });
  }
  return cols;
}

/** Expanded audit row: who/where/why metadata and the recorded values as a readable diff. */
export function AuditDetails({ event }: { event: AuditEventDto }) {
  const rows = diffRows(event.before, event.after);
  return (
    <Box className="flex flex-col gap-3">
      <KeyValueGrid
        columns={4}
        items={[
          { label: 'Entity', value: `${humanize(event.entity_type)} · ${event.entity_id}` },
          { label: 'Source', value: humanize(event.source) },
          {
            label: 'Actor roles',
            value: event.actor_roles.length === 0 ? '—' : event.actor_roles.join(', '),
          },
          { label: 'Reason', value: event.reason ?? '—' },
          { label: 'Device', value: event.device_id ?? '—' },
          { label: 'Policy version', value: event.policy_version ?? '—' },
          { label: 'Mandate', value: event.mandate_reference ?? '—' },
          { label: 'Correlation id', value: event.correlation_id },
        ]}
      />
      {rows.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No values were recorded with this event.
        </Typography>
      ) : (
        <StaticTable
          columns={columns(event)}
          rows={rows}
          getRowId={(r) => r.key}
          ariaLabel={`Recorded values for ${event.action}`}
        />
      )}
    </Box>
  );
}
