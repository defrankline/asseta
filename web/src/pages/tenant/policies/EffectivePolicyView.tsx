import { Box, Chip, Stack, Typography } from '@mui/material';
import type { EffectivePolicyDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { formatPolicyValue, TRACKING_FIELDS, type PolicyFieldDef } from './policyFields';

interface Row {
  key: string;
  def: PolicyFieldDef | undefined;
  value: unknown;
}

const columns: DataColumn<Row>[] = [
  { id: 'field', header: 'Setting', render: (r) => r.def?.label ?? r.key },
  { id: 'value', header: 'Effective value', render: (r) => formatPolicyValue(r.def, r.value) },
  {
    id: 'key',
    header: 'Key',
    render: (r) => <span className="font-mono text-xs">{r.key}</span>,
  },
];

/** Resolved policy values with the version stamp that produced them. */
export function EffectivePolicyView({ policy }: { policy: EffectivePolicyDto }) {
  const known: Row[] = TRACKING_FIELDS.map((def) => ({
    key: def.key,
    def,
    value: policy.values[def.key],
  }));
  const extra: Row[] = Object.keys(policy.values)
    .filter((k) => !TRACKING_FIELDS.some((d) => d.key === k))
    .map((key) => ({ key, def: undefined, value: policy.values[key] }));
  return (
    <Stack spacing={1}>
      <Box className="flex items-center gap-2">
        <Typography variant="body2" color="text.secondary">
          Version stamp
        </Typography>
        <Chip size="small" label={policy.version_stamp} className="font-mono" />
      </Box>
      <StaticTable
        ariaLabel="Effective policy values"
        columns={columns}
        rows={[...known, ...extra]}
        getRowId={(r) => r.key}
      />
    </Stack>
  );
}
