import { MenuItem, TextField } from '@mui/material';
import { INVOICE_STATUSES } from '../../../api/services/billingSchemas';
import type { InvoiceStatus } from '../../../api/types';
import { humanize } from '../../../utils/text';

export function InvoiceStatusFilter({
  value,
  onChange,
}: {
  value: InvoiceStatus | '';
  onChange: (v: InvoiceStatus | '') => void;
}) {
  return (
    <TextField
      select
      size="small"
      label="Status"
      value={value}
      sx={{ minWidth: 180 }}
      onChange={(e) => {
        const v = e.target.value;
        onChange(INVOICE_STATUSES.find((s) => s === v) ?? '');
      }}
    >
      <MenuItem value="">All statuses</MenuItem>
      {INVOICE_STATUSES.map((s) => (
        <MenuItem key={s} value={s}>
          {humanize(s)}
        </MenuItem>
      ))}
    </TextField>
  );
}
