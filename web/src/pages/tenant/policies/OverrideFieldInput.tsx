import { Box, Checkbox, FormControlLabel, Switch, TextField, Typography } from '@mui/material';
import { getIn, useFormikContext } from 'formik';
import type { PolicyFormValues } from './policyForm';
import { WEEKDAYS, type PolicyFieldDef } from './policyFields';

function WeekdayPicker({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled: boolean;
}) {
  const selected = new Set(value === '' ? [] : value.split(','));
  return (
    <Box className="flex flex-wrap" role="group" aria-label="Operating weekdays">
      {WEEKDAYS.map((day, i) => (
        <FormControlLabel
          key={day}
          disabled={disabled}
          control={
            <Checkbox
              size="small"
              checked={selected.has(String(i))}
              onChange={(e) => {
                const next = new Set(selected);
                if (e.target.checked) next.add(String(i));
                else next.delete(String(i));
                onChange(
                  [...next]
                    .map(Number)
                    .sort((a, b) => a - b)
                    .join(','),
                );
              }}
            />
          }
          label={day}
        />
      ))}
    </Box>
  );
}

/** One overridable policy field: an "Override" switch plus a typed input. */
export function OverrideFieldInput({ def }: { def: PolicyFieldDef }) {
  const formik = useFormikContext<PolicyFormValues>();
  const base = `overrides.${def.key}`;
  const enabled = getIn(formik.values, `${base}.enabled`) === true;
  const raw: unknown = getIn(formik.values, `${base}.value`);
  const value = typeof raw === 'string' ? raw : '';
  const errorRaw: unknown = getIn(formik.errors, `${base}.value`);
  const error = typeof errorRaw === 'string' && enabled ? errorRaw : undefined;
  const setValue = (v: string) => {
    void formik.setFieldValue(`${base}.value`, v);
  };
  return (
    <Box className="grid grid-cols-1 items-start gap-2 sm:grid-cols-[220px_1fr]">
      <FormControlLabel
        control={
          <Switch
            checked={enabled}
            onChange={(e) => {
              void formik.setFieldValue(`${base}.enabled`, e.target.checked);
            }}
            slotProps={{ input: { 'aria-label': `Override ${def.label}` } }}
          />
        }
        label={def.label}
      />
      {def.kind === 'weekdays' ? (
        <Box>
          <WeekdayPicker value={value} onChange={setValue} disabled={!enabled} />
          {error !== undefined && (
            <Typography variant="caption" color="error">
              {error}
            </Typography>
          )}
        </Box>
      ) : (
        <TextField
          size="small"
          label={def.unit !== undefined ? `${def.label} (${def.unit})` : def.label}
          value={value}
          disabled={!enabled}
          onChange={(e) => {
            setValue(e.target.value);
          }}
          placeholder={def.kind === 'time' ? 'HH:MM' : undefined}
          error={error !== undefined}
          helperText={error ?? def.help}
          slotProps={{ htmlInput: { inputMode: def.kind === 'time' ? 'text' : 'decimal' } }}
        />
      )}
    </Box>
  );
}
