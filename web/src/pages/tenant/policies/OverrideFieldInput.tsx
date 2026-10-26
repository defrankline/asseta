import {
  Box,
  Button,
  Checkbox,
  Chip,
  FormControlLabel,
  MenuItem,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import { getIn, useFormikContext } from 'formik';
import { useState } from 'react';
import type { PolicyFormValues } from './policyForm';
import { splitTimes, TIME_OF_DAY, WEEKDAYS, type PolicyFieldDef } from './policyFields';

const BOOL_OPTIONS = [
  { value: 'true', label: 'Yes' },
  { value: 'false', label: 'No' },
] as const;
const NO_OPTIONS: readonly { value: string; label: string }[] = [];

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

/** Code-defined options as checkboxes; the value is the chosen option values joined by ','. */
function MultiOptionPicker({
  def,
  value,
  onChange,
  disabled,
}: {
  def: PolicyFieldDef;
  value: string;
  onChange: (v: string) => void;
  disabled: boolean;
}) {
  const selected = new Set(value === '' ? [] : value.split(','));
  const options = def.options ?? NO_OPTIONS;
  return (
    <Box className="flex flex-wrap" role="group" aria-label={def.label}>
      {options.map((o) => (
        <FormControlLabel
          key={o.value}
          disabled={disabled}
          control={
            <Checkbox
              size="small"
              checked={selected.has(o.value)}
              onChange={(e) => {
                const next = new Set(selected);
                if (e.target.checked) next.add(o.value);
                else next.delete(o.value);
                onChange(
                  options
                    .map((x) => x.value)
                    .filter((x) => next.has(x))
                    .join(','),
                );
              }}
            />
          }
          label={o.label}
        />
      ))}
    </Box>
  );
}

/** Times of day as removable chips plus an HH:MM entry; the value is the sorted times joined by ','. */
function TimeListPicker({
  def,
  value,
  onChange,
  disabled,
}: {
  def: PolicyFieldDef;
  value: string;
  onChange: (v: string) => void;
  disabled: boolean;
}) {
  const [draft, setDraft] = useState('');
  const times = splitTimes(value);
  const entry = draft.trim();
  const valid = TIME_OF_DAY.test(entry);
  const duplicate = valid && times.includes(entry);
  const add = () => {
    if (!valid || duplicate) return;
    onChange(splitTimes([...times, entry].join(',')).join(','));
    setDraft('');
  };
  return (
    <Box className="flex flex-col gap-2" role="group" aria-label={def.label}>
      <Box className="flex flex-wrap gap-1">
        {times.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No times
          </Typography>
        ) : (
          times.map((t) => (
            <Chip
              key={t}
              label={t}
              size="small"
              disabled={disabled}
              onDelete={() => {
                onChange(times.filter((x) => x !== t).join(','));
              }}
              slotProps={{ root: { 'aria-label': `Time ${t}` } }}
            />
          ))
        )}
      </Box>
      <Box className="flex flex-wrap items-start gap-2">
        <TextField
          size="small"
          label="Add a time (HH:MM)"
          value={draft}
          disabled={disabled}
          placeholder="HH:MM"
          onChange={(e) => {
            setDraft(e.target.value);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              add();
            }
          }}
          error={entry !== '' && (!valid || duplicate)}
          helperText={
            entry === ''
              ? undefined
              : !valid
                ? 'Use HH:MM (24 h)'
                : duplicate
                  ? 'Already in the list'
                  : undefined
          }
          sx={{ maxWidth: 180 }}
        />
        <Button variant="outlined" disabled={disabled || !valid || duplicate} onClick={add}>
          Add time
        </Button>
      </Box>
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
      ) : def.kind === 'timeList' ? (
        <Box>
          <TimeListPicker def={def} value={value} onChange={setValue} disabled={!enabled} />
          {(error ?? def.help) !== undefined && (
            <Typography variant="caption" color={error !== undefined ? 'error' : 'text.secondary'}>
              {error ?? def.help}
            </Typography>
          )}
        </Box>
      ) : def.kind === 'multiEnum' ? (
        <Box>
          <MultiOptionPicker def={def} value={value} onChange={setValue} disabled={!enabled} />
          {(error ?? def.help) !== undefined && (
            <Typography variant="caption" color={error !== undefined ? 'error' : 'text.secondary'}>
              {error ?? def.help}
            </Typography>
          )}
        </Box>
      ) : def.kind === 'bool' || def.kind === 'enum' ? (
        <TextField
          select
          size="small"
          label={def.label}
          value={value}
          disabled={!enabled}
          onChange={(e) => {
            setValue(e.target.value);
          }}
          error={error !== undefined}
          helperText={error ?? def.help}
        >
          {(def.kind === 'bool' ? BOOL_OPTIONS : (def.options ?? NO_OPTIONS)).map((o) => (
            // eslint-disable-next-line no-restricted-syntax -- static: BOOL_OPTIONS or a code-defined POLICY_FIELDS enum, never backend data
            <MenuItem key={o.value} value={o.value}>
              {o.label}
            </MenuItem>
          ))}
        </TextField>
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
