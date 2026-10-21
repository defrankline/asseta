import { array, mixed, object, string, type ObjectSchema } from 'yup';
import { CAPABILITIES } from '../../../api/services/trackerSchemas';
import type {
  Capability,
  TelemetryAdapterKind,
  TrackerModelDto,
  TrackerModelIn,
  TrackerModelUpdateIn,
} from '../../../api/types';

export interface TrackerModelValues {
  manufacturer: string;
  model: string;
  protocol: string;
  adapter: TelemetryAdapterKind;
  declared_capabilities: Capability[];
  notes: string;
}

export const ADAPTER_OPTIONS: readonly { value: TelemetryAdapterKind; label: string }[] = [
  { value: 'TRACCAR', label: 'Traccar' },
];

export const MODEL_FIELDS = ['manufacturer', 'model', 'protocol', 'adapter'] as const;
export const CAPABILITY_FIELDS = ['declared_capabilities', 'notes'] as const;

export const MODEL_ERROR_HINTS: Readonly<Record<string, string>> = {
  ADAPTER_IMMUTABLE: 'The adapter cannot be changed once a model is created.',
  DUPLICATE_TRACKER_MODEL: 'This manufacturer / model / protocol is already in the catalog.',
};

export const EMPTY_MODEL: TrackerModelValues = {
  manufacturer: '',
  model: '',
  protocol: '',
  adapter: 'TRACCAR',
  declared_capabilities: ['GNSS'],
  notes: '',
};

export function valuesFromModel(m: TrackerModelDto): TrackerModelValues {
  return {
    manufacturer: m.manufacturer,
    model: m.model,
    protocol: m.protocol,
    adapter: m.adapter,
    declared_capabilities: [...m.declared_capabilities],
    notes: m.notes ?? '',
  };
}

const text = (label: string, max: number) =>
  string()
    .trim()
    .required(`${label} is required`)
    .max(max, `${label} must be at most ${String(max)} characters`);

export const trackerModelSchema: ObjectSchema<TrackerModelValues> = object({
  manufacturer: text('Manufacturer', 100),
  model: text('Model', 100),
  protocol: text('Protocol', 50),
  adapter: mixed<TelemetryAdapterKind>().oneOf(['TRACCAR']).required('Adapter is required'),
  declared_capabilities: array(mixed<Capability>().oneOf(CAPABILITIES).required())
    .required()
    .min(1, 'Declare at least one capability'),
  notes: string().trim().max(1000, 'At most 1000 characters').ensure(),
});

const orNull = (v: string): string | null => (v.trim() === '' ? null : v.trim());

function common(v: TrackerModelValues) {
  return {
    manufacturer: v.manufacturer.trim(),
    model: v.model.trim(),
    protocol: v.protocol.trim(),
    declared_capabilities: v.declared_capabilities,
    notes: orNull(v.notes),
  };
}

export function toModelCreate(v: TrackerModelValues): TrackerModelIn {
  return { ...common(v), adapter: v.adapter, approved: true };
}

export function toModelUpdate(v: TrackerModelValues, version: number): TrackerModelUpdateIn {
  return { ...common(v), version };
}

export const trackerModelLabel = (m: { manufacturer: string; model: string }) =>
  `${m.manufacturer} ${m.model}`;
