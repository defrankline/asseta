import {
  Checkbox,
  FormControl,
  FormControlLabel,
  FormGroup,
  FormHelperText,
  FormLabel,
} from '@mui/material';
import { useField } from 'formik';
import { CAPABILITIES } from '../../../api/services/trackerSchemas';
import type { Capability } from '../../../api/types';
import { CAPABILITY_LABELS } from '../../tenant/shared/display';

/** Formik checklist of the (code-defined) capability enum. */
export function CapabilityChecklist({ name }: { name: string }) {
  const [field, meta, helpers] = useField<Capability[]>(name);
  const showError = meta.touched && typeof meta.error === 'string';
  const toggle = (c: Capability, on: boolean) => {
    void helpers.setValue(on ? [...field.value, c] : field.value.filter((x) => x !== c));
    void helpers.setTouched(true, false);
  };
  return (
    <FormControl component="fieldset" error={showError}>
      <FormLabel component="legend">Declared capabilities</FormLabel>
      <FormGroup className="grid grid-cols-1 sm:grid-cols-2">
        {CAPABILITIES.map((c) => (
          <FormControlLabel
            key={c}
            label={CAPABILITY_LABELS[c]}
            control={
              <Checkbox
                checked={field.value.includes(c)}
                onChange={(e) => {
                  toggle(c, e.target.checked);
                }}
              />
            }
          />
        ))}
      </FormGroup>
      {showError && <FormHelperText>{meta.error}</FormHelperText>}
    </FormControl>
  );
}
