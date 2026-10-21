import { MenuItem, TextField } from '@mui/material';
import type { SelectOption } from './FormikSelectField';

interface StaticSelectFilterProps {
  label: string;
  value: string;
  /** A static, code-defined list (ALL_CAPS constant); backend data uses AsyncAutocomplete. */
  options: readonly SelectOption[];
  onChange: (value: string) => void;
  /** Label of the empty ("no filter") entry. */
  allLabel?: string;
  minWidth?: number;
}

/** Small list-page filter over a static enum, with an "All" entry that maps to ''. */
export function StaticSelectFilter({
  label,
  value,
  options,
  onChange,
  allLabel = 'All',
  minWidth = 180,
}: StaticSelectFilterProps) {
  return (
    <TextField
      select
      size="small"
      label={label}
      value={value}
      onChange={(e) => {
        onChange(e.target.value);
      }}
      sx={{ minWidth }}
    >
      <MenuItem value="">{allLabel}</MenuItem>
      {options.map((o) => (
        <MenuItem key={o.value} value={o.value}>
          {o.label}
        </MenuItem>
      ))}
    </TextField>
  );
}
